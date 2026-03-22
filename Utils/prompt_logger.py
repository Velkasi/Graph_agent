"""
prompt_logger.py — Capture tous les appels LLM de chaque agent
--------------------------------------------------------------
Implémente un callback LangChain qui intercepte chaque appel LLM
(y compris les itérations internes du ReAct loop) et les sauvegarde
dans runs/prompts/<agent>_<session>.jsonl

Format JSONL : une ligne JSON par appel LLM, contenant :
    - timestamp
    - agent
    - call_index  (numéro d'itération dans la session)
    - input       (messages envoyés au modèle)
    - output      (réponse reçue)
    - tokens      (usage si disponible)

Usage (automatique via BaseAgent) :
    Chaque agent héritant de BaseAgent a ses prompts loggés.
    Les fichiers sont dans runs/prompts/<agent>_<session>.jsonl

Lecture rapide :
    import json
    for line in open("runs/prompts/planner_160000.jsonl"):
        call = json.loads(line)
        print(call["input"], "→", call["output"][:100])
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


LOG_DIR = Path(__file__).parent.parent / "runs" / "prompts"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class PromptLogger(BaseCallbackHandler):
    """
    Callback LangChain qui loggue chaque appel LLM dans un fichier JSONL.
    Attaché au LLM dans BaseAgent — capture toutes les itérations ReAct.
    """

    def __init__(self, agent_name: str, session_id: str):
        super().__init__()
        self.agent_name  = agent_name
        self.session_id  = session_id
        self.call_index  = 0
        self._pending_input: list = []

        filename = f"{agent_name}_{session_id}.jsonl"
        self.log_file = LOG_DIR / filename

    def on_chat_model_start(
        self,
        serialized: dict,
        messages: list,
        **kwargs: Any,
    ) -> None:
        """Appelé juste avant l'envoi des messages au modèle."""
        self._pending_input = self._serialize_messages(messages)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Appelé après réception de la réponse — on écrit l'entrée + sortie."""
        self.call_index += 1

        output_text = ""
        try:
            output_text = response.generations[0][0].text
        except (IndexError, AttributeError):
            pass

        tokens = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            tokens = {
                "prompt":     usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total":      usage.get("total_tokens", 0),
            }

        entry = {
            "timestamp":  datetime.now().isoformat(),
            "agent":      self.agent_name,
            "call_index": self.call_index,
            "input":      self._pending_input,
            "output":     output_text,
            "tokens":     tokens,
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Loggue aussi les erreurs pour diagnostiquer les pannes."""
        entry = {
            "timestamp":  datetime.now().isoformat(),
            "agent":      self.agent_name,
            "call_index": self.call_index,
            "input":      self._pending_input,
            "error":      str(error),
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def _serialize_messages(messages: list) -> list:
        """Convertit les messages LangChain en dicts lisibles."""
        result = []
        for turn in messages:
            for msg in (turn if isinstance(turn, list) else [turn]):
                if hasattr(msg, "type") and hasattr(msg, "content"):
                    content = msg.content
                    # Tronquer les images base64 pour garder les fichiers lisibles
                    if isinstance(content, list):
                        content = [
                            {**part, "image_url": {"url": "data:[base64 tronqué]"}}
                            if part.get("type") == "image_url" else part
                            for part in content
                        ]
                    result.append({"role": msg.type, "content": content})
                else:
                    result.append({"role": "unknown", "content": str(msg)})
        return result
