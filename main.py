import sys
import os
import subprocess

def run_in_venv():
    ext_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(ext_dir, '.venv')
    requirements_file = os.path.join(ext_dir, 'requirements.txt')

    if sys.prefix == venv_dir:
        return

    if not os.path.exists(venv_dir):
        import venv
        builder = venv.EnvBuilder(with_pip=True, system_site_packages=True)
        builder.create(venv_dir)
        
        if os.path.exists(requirements_file):
            pip_exe = os.path.join(venv_dir, 'bin', 'pip')
            subprocess.check_call([pip_exe, 'install', '-r', requirements_file])

    python_exe = os.path.join(venv_dir, 'bin', 'python')
    os.execv(python_exe, [python_exe] + sys.argv)

run_in_venv()

import logging
import json
import requests
from datetime import datetime
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.OpenAction import OpenAction

logger = logging.getLogger(__name__)
EXTENSION_ICON = 'images/icon.png'

class GPTExtension(Extension):
    def __init__(self):
        super(GPTExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        kw = event.get_keyword()
        prefs = extension.preferences

        # 1. Fetch OpenRouter Models Dynamically
        if kw == prefs['model_kw']:
            return self.handle_model_search(event.get_argument())

        # 2. Select Custom Presets
        if kw == prefs['preset_kw']:
            return self.handle_preset_selection(prefs['custom_presets'])

        # 3. Standard Chat Functionality
        return self.handle_chat_query(event.get_argument(), extension)

    def handle_model_search(self, query):
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
            models = r.json().get('data', [])
            search = (query or "").lower()
            
            items = []
            for m in [m for m in models if search in m['id'].lower()][:8]:
                items.append(ExtensionResultItem(
                    icon=EXTENSION_ICON,
                    name=m['name'],
                    description=f"ID: {m['id']} (Click to copy ID)",
                    on_enter=CopyToClipboardAction(m['id'])
                ))
            return RenderResultListAction(items or [ExtensionResultItem(icon=EXTENSION_ICON, name="No models found", on_enter=DoNothingAction())])
        except Exception as e:
            return RenderResultListAction([ExtensionResultItem(icon=EXTENSION_ICON, name="API Error", description=str(e), on_enter=DoNothingAction())])

    def handle_preset_selection(self, presets_json):
        try:
            presets = json.loads(presets_json)
            items = [ExtensionResultItem(
                icon=EXTENSION_ICON,
                name=f"Preset: {name}",
                description=f"Prompt: {content[:60]}...",
                on_enter=CopyToClipboardAction(content)
            ) for name, content in presets.items()]
            return RenderResultListAction(items or [ExtensionResultItem(icon=EXTENSION_ICON, name="No presets defined in settings", on_enter=DoNothingAction())])
        except:
            return RenderResultListAction([ExtensionResultItem(icon=EXTENSION_ICON, name="JSON Error in Presets", description="Check your manifest settings", on_enter=DoNothingAction())])

    def handle_chat_query(self, prompt, extension):
        if not prompt:
            return RenderResultListAction([ExtensionResultItem(icon=EXTENSION_ICON, name="Enter your prompt...", on_enter=DoNothingAction())])

        prefs = extension.preferences
        try:
            # API Call
            headers = {"Authorization": f"Bearer {prefs['api_key']}", "Content-Type": "application/json"}
            payload = {
                "model": prefs['model'],
                "temperature": float(prefs['temperature']),
                "messages": [
                    {"role": "system", "content": prefs['system_prompt']},
                    {"role": "user", "content": prompt}
                ]
            }
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            answer = data['choices'][0]['message']['content']

            # Detailed Markdown Logging
            log_path = self.save_log(prompt, answer, data, prefs)

            return RenderResultListAction([
                ExtensionResultItem(
                    icon=EXTENSION_ICON,
                    name=f"Model: {data.get('model')}",
                    description=answer.replace('\n', ' ')[:100],
                    on_enter=CopyToClipboardAction(answer)
                ),
                ExtensionResultItem(
                    icon=EXTENSION_ICON,
                    name="Open Markdown Log",
                    description=f"Location: {os.path.basename(log_path)}",
                    on_enter=OpenAction(log_path)
                )
            ])
        except Exception as e:
            return RenderResultListAction([ExtensionResultItem(icon=EXTENSION_ICON, name="Request Failed", description=str(e), on_enter=DoNothingAction())])

    def save_log(self, prompt, answer, raw_json, prefs):
        log_dir = os.path.expanduser(prefs['log_dir'] or "~")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(log_dir, f"ai_session_{timestamp}.md")
        usage = raw_json.get('usage', {})

        markdown = f"""# AI Conversation Log - {timestamp}

## ⚙️ Metadata
- **Model:** {raw_json.get('model')}
- **Prompt Tokens:** {usage.get('prompt_tokens', 'N/A')}
- **Completion Tokens:** {usage.get('completion_tokens', 'N/A')}
- **Total Tokens:** {usage.get('total_tokens', 'N/A')}

## 👤 User Prompt
{prompt}

## 🤖 AI Response
{answer}

---
*Generated via Ulauncher AI Extension*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        return filepath

if __name__ == '__main__':
    GPTExtension().run()