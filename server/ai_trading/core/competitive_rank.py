from typing import List, Dict, Any

class CompetitiveRankCalculator:
    """
    Calculates the relative performance rank of a trading agent
    compared to a population of other agents.
    """
    def __init__(self, all_performance_data: List[Dict[str, Any]]):
        """
        Args:
            all_performance_data: List of {'agent_id': str, 'score': float}
        """
        self.data = all_performance_data
        # Sort agents by score descending
        self.sorted_data = sorted(all_performance_data, key=lambda x: x['score'], reverse=True)

    def calculate_rank(self, agent_id: str) -> int:
        """
        Calculates the ordinal rank (1-based) using standard competition ranking.
        """
        if not self.data:
            return 0

        # Find the score of the target agent
        target_score = next((item['score'] for item in self.data if item['agent_id'] == agent_id), None)

        if target_score is None:
            return len(self.data) + 1 # Rank last if not found

        # Rank is 1 + count of agents with a strictly higher score
        rank = 1 + sum(1 for item in self.data if item['score'] > target_score)
        return rank

    def format_rank_string(self, agent_id: str) -> str:
        """
        Returns a human-readable rank string for the LLM.
        Example: "Rank 3rd out of 10 agents"
        """
        rank = self.calculate_rank(agent_id)
        total = len(self.data)

        if total == 0:
            return "Rank Unknown"

        # Ordinal suffix logic
        if 11 <= (rank % 100) <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")

        return f"Rank {rank}{suffix} out of {total} agents"
