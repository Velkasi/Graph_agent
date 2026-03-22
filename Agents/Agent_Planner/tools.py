"""
tools.py — PlannerAgent
-----------------------
Pas de tools pour ce agent.

Vision   : les maquettes UX sont passées directement dans le message
           multimodal initial — qwen3.5-9b les voit nativement.

Validation : déléguée au ReviewAgent dans la boucle de correction LangGraph.
             Le PlannerAgent produit la spec ; c'est au ReviewAgent de rejeter
             et demander une correction si elle est incomplète.
"""
