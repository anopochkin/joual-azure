
import os
import json
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from openai import AzureOpenAI  # Utilise la nouvelle bibliothèque openai >= 1.0.0

# --- CONFIGURATION AVEC VOS DONNÉES ---
KEY_VAULT_NAME = "keys-joual" 
OPENAI_API_SECRET_NAME = "openaiapikey"  # Nom du secret dans Key Vault
AZURE_OPENAI_ENDPOINT = "https://openai-test-joual.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-35-turbo"
API_VERSION = "2024-02-01"
# --- Fin de la configuration ---

# --- Variables globales pour les clients ---
openai_api_key = None
client = None  # Client Azure OpenAI

# --- Fonction pour récupérer la clé API OpenAI ---
def recuperer_cle_openai():
    global openai_api_key
    print(f"INFO : Tentative d'authentification au Key Vault : {KEY_VAULT_NAME}...")
    try:
        credential = ManagedIdentityCredential()
        print("INFO : ManagedIdentityCredential créée.")
        key_vault_url = f"https://{KEY_VAULT_NAME}.vault.azure.net/"
        kv_client = SecretClient(vault_url=key_vault_url, credential=credential)
        print(f"INFO : Client Key Vault créé pour {key_vault_url}.")
        print(f"INFO : Récupération du secret '{OPENAI_API_SECRET_NAME}'...")
        retrieved_secret = kv_client.get_secret(OPENAI_API_SECRET_NAME)
        openai_api_key = retrieved_secret.value
        print("INFO : Clé API OpenAI récupérée avec succès.")
        return True
    except Exception as e:
        print(f"ERREUR : Échec de récupération du secret : {e}")
        print("INFO : Vérifiez que la machine virtuelle dispose d'une identité managée et du rôle 'Utilisateur de secrets Key Vault'.")
        return False

# --- Fonction d'initialisation du client OpenAI ---
def initialiser_client_openai():
    global client
    if not openai_api_key:
        print("ERREUR : Clé API OpenAI manquante. Impossible d'initialiser le client.")
        return False

    print(f"INFO : Initialisation du client Azure OpenAI pour l'endpoint : {AZURE_OPENAI_ENDPOINT}...")
    try:
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=openai_api_key,
            api_version=API_VERSION
        )
        print("INFO : Client Azure OpenAI initialisé.")
        return True
    except Exception as e:
        print(f"ERREUR : Échec de l'initialisation du client OpenAI : {e}")
        return False

# --- Chargement d'un prompt depuis un fichier ---
def charger_prompt(nom_style):
    nom_fichier = f"prompt_{nom_style.lower()}.txt"
    chemin = os.path.join("prompts", nom_fichier)
    print(f"INFO : Chargement du prompt depuis : {chemin}")
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"AVERTISSEMENT : Fichier prompt non trouvé à {chemin}. Utilisation d’un prompt de base.")
        return f"Réécris le texte suivant dans le style '{nom_style}' :\n\"\"\"\n{{text_input}}\n\"\"\"\n\nTexte en style {nom_style}:"

# --- Fonction principale de transformation ---
def transformer_texte(texte_original, style):
    global client
    if not client:
        print("ERREUR : Le client OpenAI n’est pas initialisé.")
        return "Erreur : client OpenAI non initialisé."
    
    print(f"\nINFO : Transformation du texte en style : '{style}'...")
    prompt_template = charger_prompt(style)

    if "{text_input}" not in prompt_template:
        print(f"AVERTISSEMENT : Placeholder '{{text_input}}' non trouvé. Ajout manuel du texte.")
        prompt = prompt_template + "\n\nTexte original :\n" + texte_original
    else:
        prompt = prompt_template.format(text_input=texte_original)
        
    print(f"INFO : Utilisation du prompt (150 premiers caractères) : {prompt[:150]}...")

    try:
        print(f"INFO : Appel à Azure OpenAI avec le déploiement '{AZURE_OPENAI_DEPLOYMENT_NAME}'...")
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )

        if response.choices:
            texte_genere = response.choices[0].message.content.strip()
            print("INFO : Transformation réussie.")
            return texte_genere
        else:
            print("AVERTISSEMENT : Aucune réponse générée.")
            return "Erreur : aucune réponse générée."

    except Exception as e:
        print(f"ERREUR : Erreur lors de l'appel API OpenAI : {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"DÉTAILS DE L'ERREUR : {e.response.text}")
        return "Erreur lors de l'appel API OpenAI."

# --- Bloc principal ---
if __name__ == "__main__":

    if not recuperer_cle_openai():
        exit()

    if not initialiser_client_openai():
        exit()

    if not os.path.exists("prompts"):
        print("INFO : Création du répertoire 'prompts'.")
        os.makedirs("prompts")
        prompts_defaut = {
            "joual": "Agis comme un expert en linguistique québécoise. Réécris le texte suivant en utilisant abondamment le joual et des sacres légers si approprié. Sois naturel et garde le sens original.\nTexte :\n\"\"\"\n{text_input}\n\"\"\"\n\nTexte en Joual :",
            "litteraire": "Agis comme un écrivain académique. Réécris le texte suivant dans un style littéraire soutenu, en utilisant un vocabulaire riche et des phrases élaborées. Garde le sens original.\nTexte :\n\"\"\"\n{text_input}\n\"\"\"\n\nTexte Littéraire :"
        }
        for style, contenu in prompts_defaut.items():
            chemin_fichier = os.path.join("prompts", f"prompt_{style}.txt")
            if not os.path.exists(chemin_fichier):
                print(f"INFO : Création du fichier de prompt par défaut : {chemin_fichier}")
                with open(chemin_fichier, 'w', encoding='utf-8') as f:
                    f.write(contenu)

    print("\n" + "="*30)
    print("Transformation de style de texte en français")
    print("Appuyez sur Entrée sans texte pour quitter.")
    print("="*30)

    while True:
        try:
            texte_utilisateur = input("Entrez le texte à transformer :\n> ").strip()
            if not texte_utilisateur:
                print("Aucun texte saisi. Fin du programme.")
                break

            styles = ["joual", "litteraire", "argot", "familier"]

            print("\n--- Transformation en cours... ---")

            for style in styles:
                texte_transforme = transformer_texte(texte_utilisateur, style)
                print("-" * 20)
                print(f"Style ciblé : {style}")
                print(f"Texte transformé : {texte_transforme}")
                print("-" * 20)

            print("\n--- Transformation terminée. Entrez un nouveau texte ou appuyez sur Entrée pour quitter. ---")

        except EOFError:
            print("\nFin demandée. À bientôt !")
            break
        except KeyboardInterrupt:
            print("\nInterruption par l'utilisateur. À bientôt !")
            break

    print("\n" + "="*30)
    print("Programme terminé.")
    print("="*30)
