"""
agent.py — PlannerAgent
------------------------
Premier agent du pipeline. Transforme un prompt utilisateur + maquettes UX
en spécification produit structurée (spec riche).

Modèle : qwen/qwen3.5-9b  (config_qwen)
  - Vision   : les maquettes UX sont passées inline dans le message multimodal
  - Thinking : le modèle raisonne dans des balises <think>...</think> avant de
               produire le JSON → ces balises sont strippées avant le parsing

Pas de tools ni de boucle ReAct :
  - La vision est native (images dans le message)
  - La validation/correction est gérée par le ReviewAgent en aval

Sortie : dict spec riche → devient state["spec"] → nourrit l'ArchitectAgent
"""

import json
import re
import base64
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from Agents.base_agent import BaseAgent


# ===========================================================================
# SYSTEM PROMPT
# ===========================================================================

SYSTEM_PROMPT = """Tu es PlannerAgent, premier agent d'une pipeline multi-agents qui génère des applications mobiles professionnelles (React Native / Expo / Supabase).

TON RÔLE :
Analyser le prompt utilisateur (et les maquettes UX si présentes) pour produire une spécification produit complète et structurée.

Cette spec est la FONDATION de tout le projet. Elle sera lue par l'ArchitectAgent pour concevoir l'architecture technique, puis par tous les agents en aval. Sois exhaustif.

RÈGLES :
- Chaque écran doit avoir un nom clair, une description et ses actions clés
- Les data_entities sont les futures tables Supabase (entités métier uniquement, pas les tables système)
- Déduis intelligemment ce qui n'est pas dit (ex: si auth=true → ajouter écran "Connexion" et entité "users")
- Si des maquettes sont fournies, base-toi sur ce que tu vois pour enrichir la spec
- Reste concis sur tech_constraints : ce sont des contraintes réelles, pas des voeux

FORMAT DE SORTIE :
Réponds UNIQUEMENT avec le JSON brut. Pas de balises markdown. Pas de texte avant ou après.
Respecte exactement cette structure :

{
  "app_name": "string",
  "description": "string — 1 à 2 phrases",
  "target_users": "string — qui utilise l'app et dans quel contexte",
  "screens": [
    {
      "name": "string",
      "description": "string — ce que l'écran fait",
      "key_actions": ["action1", "action2"]
    }
  ],
  "features": ["string"],
  "auth": true,
  "roles": ["string — ex: user, admin, moderator"],
  "data_entities": ["string — ex: task, project, comment"],
  "tech_constraints": "string — ex: offline-first, realtime, multi-tenant",
  "monetization": "string — ex: freemium, abonnement, gratuit",
  "priority": "v1"
}"""


# ===========================================================================
# UTILITAIRES
# ===========================================================================

def _encode_image(image_path: str) -> str | None:
    """Encode une image en base64. Retourne None si le fichier est inaccessible."""
    path = Path(image_path)
    if not path.exists():
        print(f"  [PlannerAgent] Image introuvable : {image_path}")
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"  [PlannerAgent] Erreur lecture image '{image_path}' : {e}")
        return None


def _mime_type(image_path: str) -> str:
    """Retourne le MIME type selon l'extension du fichier image."""
    ext = Path(image_path).suffix.lower().lstrip(".")
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")


def _strip_thinking(text: str) -> str:
    """
    Supprime les balises <think>...</think> produites par le mode thinking de Qwen.
    Retourne uniquement le contenu après le raisonnement.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_spec_json(text: str) -> dict:
    """
    Extrait et parse le JSON de la réponse du LLM.
    Tente 3 stratégies de fallback pour gérer les formats imprévus.
    """
    # Supprimer le thinking avant tout
    text = _strip_thinking(text)

    # Essai 1 : parse direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Essai 2 : extraire un bloc ```json ... ``` ou ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Essai 3 : trouver le premier objet JSON { ... } complet
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback : préserver la réponse brute pour debug
    print("  [PlannerAgent] ⚠ Impossible de parser le JSON — réponse brute conservée")
    return {"status": "parse_error", "raw": text}


# ===========================================================================
# AGENT
# ===========================================================================

class AgentPlanner(BaseAgent):
    """
    PlannerAgent — traduit un prompt utilisateur + maquettes en spec produit.

    Utilise qwen3.5-9b (vision + thinking) :
      - Passe les images directement dans le message multimodal
      - Le mode thinking génère un raisonnement interne avant le JSON final

    Usage depuis graph.py (planner_node) :
        agent = AgentPlanner()
        spec = agent.run(
            prompt="Une app de gestion de tâches collaborative pour équipes",
            ux_images=["maquettes/home.png", "maquettes/detail.png"]
        )
        # → {"app_name": "...", "screens": [...], "features": [...], ...}
    """

    def __init__(self):
        super().__init__("config_qwen")
        print("[PlannerAgent] Prêt — qwen3.5-9b (vision + thinking).")

    def run(self, prompt: str, ux_images: list[str] | None = None) -> dict:
        """
        Génère la spec produit.

        Args:
            prompt     : description libre de l'application à construire
            ux_images  : chemins vers les maquettes UX (optionnel)

        Returns:
            dict — spec structurée prête pour l'ArchitectAgent
        """
        ux_images = ux_images or []

        # --- Construction du message multimodal ---
        images_hint = (
            f"\n\n{len(ux_images)} maquette(s) UX jointe(s). "
            "Analyse-les pour enrichir la spec (écrans, composants, flux de navigation)."
            if ux_images else ""
        )

        content: list = [{
            "type": "text",
            "text": f"Génère la spec produit pour l'application suivante :\n\n{prompt}{images_hint}"
        }]

        # Ajout des images encodées en base64
        images_loaded = 0
        for img_path in ux_images:
            b64 = _encode_image(img_path)
            if b64:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{_mime_type(img_path)};base64,{b64}"}
                })
                images_loaded += 1

        if ux_images:
            print(f"  [PlannerAgent] {images_loaded}/{len(ux_images)} image(s) chargée(s)")

        # --- Appel LLM ---
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]

        print("  [PlannerAgent] Génération de la spec en cours...")
        response = self.llm.invoke(messages)

        # --- Parse du JSON (avec gestion du thinking) ---
        spec = _parse_spec_json(response.content)

        if "app_name" in spec:
            n_screens = len(spec.get("screens", []))
            n_features = len(spec.get("features", []))
            print(f"  [PlannerAgent] ✓ Spec générée : '{spec['app_name']}' — {n_screens} écrans, {n_features} features")

        return spec
