"""
State — Quản lý trạng thái bot (watchlist, params, alert config)
"""

import json
import os

STATE_FILE = "bot_state.json"

DEFAULT_PARAMS = {
    "rsi_len":      7,
    "ema_fast":     21,
    "ema_slow":     49,
    "stoch_len":    14,
    "smooth_k":     3,
    "smooth_d":     3,
    "ob_level":     70,
    "os_level":     30,
    "stoch_ob":     80,
    "stoch_os":     20,
    "macd_fast":    12,
    "macd_slow":    26,
    "macd_signal":  9,
    "lookback_bars": 8,
    "macd_confirm": False,
}

DEFAULT_WATCHLIST = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]


class BotState:
    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "watchlist":      list(DEFAULT_WATCHLIST),
            "params":         dict(DEFAULT_PARAMS),
            "alert_enabled":  False,
            "alert_interval": 15,
            "alert_chat_ids": [],
            "min_volume":     1_000_000,
        }

    def _save(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    # ── Watchlist ──
    @property
    def watchlist(self) -> list:
        return self._data.get("watchlist", list(DEFAULT_WATCHLIST))

    def add_symbol(self, symbol: str):
        if symbol not in self._data["watchlist"]:
            self._data["watchlist"].append(symbol)
            self._save()

    def remove_symbol(self, symbol: str):
        self._data["watchlist"] = [s for s in self._data["watchlist"] if s != symbol]
        self._save()

    # ── Params ──
    @property
    def params(self) -> dict:
        return self._data.get("params", dict(DEFAULT_PARAMS))

    @params.setter
    def params(self, value: dict):
        self._data["params"] = value
        self._save()

    # ── Alert ──
    @property
    def alert_enabled(self) -> bool:
        return self._data.get("alert_enabled", False)

    @alert_enabled.setter
    def alert_enabled(self, value: bool):
        self._data["alert_enabled"] = value
        self._save()

    @property
    def alert_interval(self) -> int:
        return self._data.get("alert_interval", 15)

    @alert_interval.setter
    def alert_interval(self, value: int):
        self._data["alert_interval"] = value
        self._save()

    @property
    def alert_chat_ids(self) -> list:
        return self._data.get("alert_chat_ids", [])

    def add_chat_id(self, chat_id: int):
        if chat_id not in self._data["alert_chat_ids"]:
            self._data["alert_chat_ids"].append(chat_id)
            self._save()

    # ── Volume filter ──
    @property
    def min_volume(self) -> float:
        return self._data.get("min_volume", 1_000_000)

    @min_volume.setter
    def min_volume(self, value: float):
        self._data["min_volume"] = value
        self._save()
