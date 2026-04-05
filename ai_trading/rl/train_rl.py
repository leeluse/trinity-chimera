"""PPO Reinforcement Learning Training Script for NIM-TRADE.

This module implements PPO training for trading agents using stable-baselines3.
Handles training, evaluation, checkpointing, and monitoring.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional, Union

import gymnasium as gym
import numpy as np
import pandas as pd
import torch
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CallbackList,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class PPOConfig:
    """PPO Training Configuration.

    Attributes:
        learning_rate: Adam optimizer learning rate
        n_steps: Number of steps to collect before update
        batch_size: Minibatch size for updates
        n_epochs: Number of epochs per update
        gamma: Discount factor
        gae_lambda: GAE lambda for advantage estimation
        clip_range: Clipping parameter epsilon
        ent_coef: Entropy coefficient for exploration
        vf_coef: Value function loss coefficient
        max_grad_norm: Maximum gradient norm for clipping
        total_timesteps: Total training steps
        eval_freq: Evaluation frequency (steps)
        save_freq: Checkpoint save frequency (steps)
        log_dir: Directory for logs
        checkpoint_dir: Directory for checkpoints
        seed: Random seed for reproducibility
        device: Device for training (cpu/cuda/auto)
    """
    # PPO hyperparameters
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5

    # Training settings
    total_timesteps: int = 1_000_000
    eval_freq: int = 10_000
    save_freq: int = 50_000

    # Paths
    log_dir: str = "./logs"
    checkpoint_dir: str = "./checkpoints"
    model_dir: str = "./models"

    # Misc
    seed: int = 42
    device: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


class TensorBoardMetricsCallback(BaseCallback):
    """Custom callback for logging additional metrics to TensorBoard."""

    def __init__(self, log_interval: int = 1000, verbose: int = 0):
        super().__init__(verbose)
        self.log_interval = log_interval
        self.episode_rewards = []
        self.episode_lengths = []

    def _on_step(self) -> bool:
        """Called at each step."""
        if len(self.model.ep_info_buffer) > 0:
            # Log episode statistics
            if self.num_timesteps % self.log_interval == 0:
                for info in self.model.ep_info_buffer:
                    if "episode" in info:
                        self.logger.record(
                            "episode/reward_mean",
                            info["episode"]["r"]
                        )
                        self.logger.record(
                            "episode/length_mean",
                            info["episode"]["l"]
                        )

        return True


class BestModelSaveCallback(BaseCallback):
    """Callback to save best model based on evaluation mean reward."""

    def __init__(self, save_path: str, verbose: int = 0):
        super().__init__(verbose)
        self.save_path = Path(save_path)
        self.best_mean_reward = -float("inf")
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        """Check and save best model."""
        if self.parent is None:
            return True

        # Access evaluation results from parent callback
        if hasattr(self.parent, "last_mean_reward"):
            mean_reward = self.parent.last_mean_reward
            if mean_reward > self.best_mean_reward:
                self.best_mean_reward = mean_reward
                self.model.save(self.save_path)
                if self.verbose > 0:
                    logger.info(
                        f"New best model saved! Mean reward: {mean_reward:.2f}"
                    )

        return True


def create_env(config: dict[str, Any]) -> gym.Env:
    """Create trading environment.

    Args:
        config: Environment configuration

    Returns:
        Gymnasium environment
    """
    # Import environment (placeholder for John's implementation)
    try:
        from ai_trading.rl.trading_env import CryptoTradingEnv
        env = CryptoTradingEnv(config)
    except ImportError:
        logger.warning(
            "CryptoTradingEnv not found. Using Dummy environment for testing."
        )
        from ai_trading.rl.dummy_env import DummyTradingEnv
        env = DummyTradingEnv(config)

    return env


def make_vec_env(
    config: dict[str, Any],
    n_envs: int = 1,
    seed: int = 42,
    normalize: bool = True,
    normalize_kwargs: Optional[dict] = None
) -> VecNormalize:
    """Create vectorized environment with normalization.

    Args:
        config: Environment configuration
        n_envs: Number of parallel environments
        seed: Random seed
        normalize: Whether to use VecNormalize
        normalize_kwargs: Additional args for VecNormalize

    Returns:
        Vectorized environment
    """
    # Environment factory
    def env_fn():
        env = create_env(config)
        env = Monitor(env)
        env.reset(seed=seed)
        return env

    # Create vectorized environment
    if n_envs == 1:
        vec_env = DummyVecEnv([env_fn])
    else:
        from stable_baselines3.common.vec_env import SubprocVecEnv
        vec_env = SubprocVecEnv([env_fn for _ in range(n_envs)])

    # Wrap with VecNormalize
    if normalize:
        normalize_kwargs = normalize_kwargs or {}
        vec_env = VecNormalize(
            vec_env,
            norm_obs=True,
            norm_reward=True,
            clip_obs=10.0,
            clip_reward=10.0,
            gamma=config.get("gamma", 0.99),
            **normalize_kwargs
        )

    return vec_env


def linear_schedule(initial_value: float, min_value: float = 1e-7):
    """Create linear learning rate schedule.

    Args:
        initial_value: Initial learning rate
        min_value: Minimum learning rate

    Returns:
        Learning rate schedule function
    """
    def func(progress_remaining: float) -> float:
        """Linear decay from initial to min value."""
        return max(min_value, initial_value * progress_remaining)
    return func


def train_ppo(
    config: PPOConfig,
    env_config: dict[str, Any],
    env_type: str = "momentum",
    n_envs: int = 1,
    continue_training: Optional[str] = None
) -> PPO:
    """Train PPO agent.

    Args:
        config: PPO training configuration
        env_config: Environment configuration
        env_type: Agent type (momentum/mean_reversion/macro/chaos)
        n_envs: Number of parallel environments
        continue_training: Path to continue training from (optional)

    Returns:
        Trained PPO model
    """
    # Set random seed
    set_random_seed(config.seed)

    # Create directories
    log_dir = Path(config.log_dir) / env_type
    checkpoint_dir = Path(config.checkpoint_dir) / env_type
    model_dir = Path(config.model_dir) / env_type

    for dir_path in [log_dir, checkpoint_dir, model_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Create environments
    logger.info("Creating environments...")
    train_env = make_vec_env(
        env_config,
        n_envs=n_envs,
        seed=config.seed,
        normalize=True,
        normalize_kwargs={"training": True}
    )

    eval_env = make_vec_env(
        env_config,
        n_envs=1,
        seed=config.seed + 1000,
        normalize=True,
        normalize_kwargs={"training": False}
    )

    # Load normalization statistics if continuing
    if continue_training:
        norm_path = Path(continue_training).parent / "vec_normalize.pkl"
        if norm_path.exists():
            train_env = VecNormalize.load(str(norm_path), train_env)
            eval_env = VecNormalize.load(str(norm_path), eval_env)
            logger.info(f"Loaded normalization from {norm_path}")

    # Configure TensorBoard logging
    logger.info("Configuring TensorBoard logging...")
    log_file = configure(log_dir, ["stdout", "tensorboard"])

    # Create or load model
    if continue_training:
        logger.info(f"Continuing training from {continue_training}")
        model = PPO.load(
            continue_training,
            env=train_env,
            device=config.device,
            tensorboard_log=str(log_dir / "tensorboard")
        )
    else:
        logger.info("Creating new PPO model...")

        # Optional: learning rate schedule
        lr_schedule_fn = linear_schedule(config.learning_rate)

        model = PPO(
            policy="MlpPolicy",
            env=train_env,
            learning_rate=config.learning_rate,  # or lr_schedule_fn
            n_steps=config.n_steps,
            batch_size=config.batch_size,
            n_epochs=config.n_epochs,
            gamma=config.gamma,
            gae_lambda=config.gae_lambda,
            clip_range=config.clip_range,
            ent_coef=config.ent_coef,
            vf_coef=config.vf_coef,
            max_grad_norm=config.max_grad_norm,
            tensorboard_log=str(log_dir / "tensorboard"),
            device=config.device,
            verbose=1,
        )

    # Setup callbacks
    callbacks = []

    # Evaluation callback
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=str(model_dir),
        log_path=str(log_dir / "eval"),
        eval_freq=config.eval_freq,
        deterministic=True,
        render=False,
        n_eval_episodes=5,
    )
    callbacks.append(eval_callback)

    # Checkpoint callback
    checkpoint_callback = CheckpointCallback(
        save_freq=config.save_freq,
        save_path=str(checkpoint_dir),
        name_prefix=f"ppo_{env_type}",
        save_vecnormalize=True,
    )
    callbacks.append(checkpoint_callback)

    # Custom metrics callback
    metrics_callback = TensorBoardMetricsCallback(log_interval=1000)
    callbacks.append(metrics_callback)

    callback = CallbackList(callbacks)

    # Save config
    config_path = model_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)
    logger.info(f"Saved config to {config_path}")

    # Train
    logger.info(f"Starting training for {config.total_timesteps} timesteps...")
    try:
        model.learn(
            total_timesteps=config.total_timesteps,
            callback=callback,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        logger.info("Training interrupted by user")

    # Save final model
    final_model_path = model_dir / "final_model"
    model.save(final_model_path)
    logger.info(f"Saved final model to {final_model_path}")

    # Save VecNormalize statistics
    train_env.save(str(model_dir / "vec_normalize.pkl"))
    logger.info("Saved normalization statistics")

    return model


def evaluate_model(
    model_path: str,
    env_config: dict[str, Any],
    n_episodes: int = 10,
    deterministic: bool = True
) -> dict[str, Any]:
    """Evaluate trained model.

    Args:
        model_path: Path to saved model
        env_config: Environment configuration
        n_episodes: Number of evaluation episodes
        deterministic: Whether to use deterministic policy

    Returns:
        Dictionary of evaluation metrics
    """
    logger.info(f"Evaluating model from {model_path}...")

    # Load model
    model = PPO.load(model_path)

    # Create evaluation environment
    eval_env = make_vec_env(
        env_config,
        n_envs=1,
        normalize=True,
        normalize_kwargs={"training": False}
    )

    # Load normalization statistics if available
    norm_path = Path(model_path).parent / "vec_normalize.pkl"
    if norm_path.exists():
        eval_env = VecNormalize.load(str(norm_path), eval_env)
        eval_env.training = False
        eval_env.norm_reward = False  # Don't normalize rewards during eval

    # Run evaluation
    episode_rewards = []
    episode_lengths = []

    for episode in range(n_episodes):
        obs = eval_env.reset()
        done = False
        episode_reward = 0.0
        episode_length = 0

        while not done:
            action, _ = model.predict(obs, deterministic=deterministic)
            obs, reward, done, info = eval_env.step(action)
            episode_reward += reward[0]
            episode_length += 1

        episode_rewards.append(episode_reward)
        episode_lengths.append(episode_length)
        logger.info(f"Episode {episode + 1}: Reward = {episode_reward:.2f}")

    # Calculate statistics
    results = {
        "mean_reward": float(np.mean(episode_rewards)),
        "std_reward": float(np.std(episode_rewards)),
        "min_reward": float(np.min(episode_rewards)),
        "max_reward": float(np.max(episode_rewards)),
        "mean_length": float(np.mean(episode_lengths)),
        "n_episodes": n_episodes,
    }

    logger.info(f"Mean reward: {results['mean_reward']:.2f} +/- {results['std_reward']:.2f}")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Train PPO trading agent")
    parser.add_argument(
        "--agent-type",
        type=str,
        default="momentum_hunter",
        choices=["momentum_hunter", "mean_reverter", "macro_trader", "chaos_agent"],
        help="Agent type to train"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config JSON file"
    )
    parser.add_argument(
        "--continue-from",
        type=str,
        default=None,
        help="Path to model to continue training from"
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Only evaluate model, don't train"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Model path for evaluation"
    )
    parser.add_argument(
        "--n-envs",
        type=int,
        default=1,
        help="Number of parallel environments"
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=1_000_000,
        help="Total training timesteps"
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            ppo_config_dict = json.load(f)
        ppo_config = PPOConfig(**ppo_config_dict)
    else:
        ppo_config = PPOConfig(total_timesteps=args.timesteps)

    # Environment configuration (placeholder)
    env_config = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "initial_balance": 10000,
        "fee": 0.001,
        "slippage": 0.0005,
        "window_size": 20,
        "gamma": ppo_config.gamma,
    }

    # Evaluate or train
    if args.eval_only:
        if args.model_path is None:
            raise ValueError("--model-path required for evaluation")
        results = evaluate_model(args.model_path, env_config)
        print(json.dumps(results, indent=2))
    else:
        model = train_ppo(
            ppo_config,
            env_config,
            env_type=args.agent_type.replace("_", ""),
            n_envs=args.n_envs,
            continue_training=args.continue_from
        )
        print(f"Training complete!")


if __name__ == "__main__":
    main()
