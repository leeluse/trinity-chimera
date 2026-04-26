import { fetchWithBypass, API_BASE_URL } from "./fetcher";
import * as T from "./types";



export class BackendAPI {








  static async getAutomationStatus(): Promise<{ enabled: boolean, status: string }> {
    const response = await fetchWithBypass(`${API_BASE_URL}/system/automation`);
    if (!response.ok) throw new Error("Failed to fetch automation status");
    return response.json();
  }

  static async setAutomationStatus(enabled: boolean): Promise<{ success: boolean, enabled: boolean }> {
    const response = await fetchWithBypass(`${API_BASE_URL}/system/automation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!response.ok) throw new Error("자동화 상태 변경 실패");
    return response.json();
  }

  static async fetchStrategies(): Promise<any[]> {
    try {
      const res = await fetchWithBypass(`${API_BASE_URL}/backtest/strategies`);
      const data = await res.json();
      return data.success ? data.strategies : [];
    } catch (error) {
      console.error("Failed to fetch strategies:", error);
      return [];
    }
  }

  static async fetchBots(): Promise<any[]> {
    try {
      const res = await fetchWithBypass(`${API_BASE_URL}/bots`);
      const data = await res.json();
      if (Array.isArray(data)) return data;
      return data && data.success && Array.isArray(data.bots) ? data.bots : [];
    } catch (error) {
      console.error("Failed to fetch bots:", error);
      return [];
    }
  }

  static async createBot(config: T.BotConfig): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    return res.json();
  }

  static async getBot(botId: string): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`);
    return res.json();
  }

  static async updateBot(botId: string, updates: Partial<T.BotConfig>): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    return res.json();
  }

  static async deleteBot(botId: string): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`, {
      method: "DELETE",
    });
    return res.json();
  }

  static async startBot(botId: string): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/start`, {
      method: "POST",
    });
    return res.json();
  }

  static async stopBot(botId: string): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/stop`, {
      method: "POST",
    });
    return res.json();
  }

  static async getBotState(botId: string): Promise<any> {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/state`);
    return res.json();
  }

  static async fetchBotTrades(limit = 50): Promise<any[]> {
    try {
      const res = await fetchWithBypass(`${API_BASE_URL}/bots/trades?limit=${limit}`);
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    } catch (error) {
      console.error("Failed to fetch bot trades:", error);
      return [];
    }
  }
}

// Standalone exports for compatibility
export const fetchStrategies = BackendAPI.fetchStrategies;
export const fetchBots = BackendAPI.fetchBots;
export const createBot = BackendAPI.createBot;
export const getBot = BackendAPI.getBot;
export const updateBot = BackendAPI.updateBot;
export const deleteBot = BackendAPI.deleteBot;
export const startBot = BackendAPI.startBot;
export const stopBot = BackendAPI.stopBot;
export const getBotState = BackendAPI.getBotState;
export const fetchBotTrades = BackendAPI.fetchBotTrades;
