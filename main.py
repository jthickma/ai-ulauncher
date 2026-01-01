import logging
import os
import datetime
import json
import time
import glob
import shutil  # For moving files if needed, but here for cleanup
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
import requests

logger = logging.getLogger(__name__)
EXTENSION_ICON = 'images/icon.png'
IMAGE_GEN_ENDPOINT = "https://api-inference.huggingface.co/models/cyberagent/openverse-style"  # Placeholder for DALL-E mini

# Localization dictionaries (English only)
LOCALES = {
    'en': {
        'clear_success': 'Conversation history cleared',
        'no_history': 'No history available.',
        'export_success': 'Full log exported',
        'no_history_export': 'No history to export',
        'blank_prompt': 'Type a prompt, or try "clear history", "view history", "export full log", "generate image [prompt]"...',
        'request_failed': 'Request failed',
        'parse_error': 'Parse error',
        'image_generated': 'Image generated'
    }
}

def wrap_text(text: str, max_w: int, theme: str) -> str:
    """Wrap text with theme adjustments (e.g., dark theme adds bold for contrast)."""
    wrapped = wrap_text_basic(text, max_w)
    if theme == 'dark':
        # Simulate visual styling by adding markdown-like bold
        wrapped = '**' + wrapped.replace('\n', '**<br>**') + '**'
    return wrapped

def wrap_text_basic(text: str, max_w: int) -> str:
    """Basic text wrapping."""
    if max_w <= 0:
        return text
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        if len(current_line + word) <= max_w:
            current_line += ' ' + word
        else:
            if current_line:
                lines.append(current_line.strip())
            if len(word) > max_w:
                while len(word) > max_w:
                    lines.append(word[:max_w])
                    word = word[max_w:]
                current_line = word
            else:
                current_line = word
    if current_line:
        lines.append(current_line.strip())
    return '\n'.join(lines)

def generate_image(prompt: str, api_key: str, theme: str) -> str:
    """Generate image using external API (placeholder)."""
    try:
        response = requests.post(IMAGE_GEN_ENDPOINT, headers={'Authorization': f'Bearer {api_key}'}, json={"inputs": prompt}, timeout=15)
        if response.status_code == 200:
            # Assuming response contains image URL, copy to clipboard
            return response.json()['url']  # Placeholder
        else:
            return f"Image gen failed: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

def cleanup_old_logs(directory: str, days: int):
    """Delete logs older than specified days."""
    if days <= 0:
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    pattern = os.path.join(directory, "ai_conversation_*.md")
    for filepath in glob.glob(pattern):
        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        if timestamp < cutoff:
            try:
                os.remove(filepath)
                logger.info(f"Deleted old log: {filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete {filepath}: {e}")

def create_log_md(conversation_history: list, model: str, system_prompt: str, temperature: float,
                  user_prompt: str, ai_response: str, wrap_len: int, endpoint: str,
                  response_time: float, error: str = None, lang: str = 'en') -> str:
    """Generate structured Markdown log with localization."""
    loc = LOCALES.get(lang, LOCALES['en'])
    timestamp = datetime.datetime.now().isoformat()
    history_md = "#### Full Conversation History\n"
    for exchange in conversation_history:
        history_md += f"- **User**: {exchange['user']}\n- **AI**: {exchange['ai']}\n\n"

    log_content = f"""# AI Conversation Log

**Timestamp:** {timestamp}  
**Model:** {model}  
**System Prompt:** {system_prompt}  
**Temperature:** {temperature}  
**Line Wrap Length:** {wrap_len}  
**API Endpoint:** {endpoint}  
**Response Time (seconds):** {response_time:.2f}  
**Language:** {lang}  

{history_md}

#### Latest Exchange  
**User Prompt:** {user_prompt}  
**AI Response:** {ai_response}  

"""
    if error:
        log_content += f"**Error:** {error}\n"
    return log_content

def save_log(directory: str, log_content: str) -> str:
    """Save log; create dir if needed."""
    try:
        os.makedirs(directory, exist_ok=True)
        filename = f"ai_conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(log_content)
        return filepath
    except Exception as e:
        logger.error(f"Failed to save log: {e}")
        return f"Error: {e}"

class GPTExtension(Extension):
    api_call_count = 0  # Track API calls for quota simulation
    def __init__(self):
        self.conversation_history = []  # Now instance-level for modularity
        super(GPTExtension, self).__init__()
        logger.info('AI extension started')

    def run(self):
        # Cleanup on start
        try:
            log_directory = os.path.expanduser(self.preferences.get('log_directory', '~'))
            cleanup_days = int(self.preferences.get('log_cleanup_days', '7'))
            cleanup_old_logs(log_directory, cleanup_days)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        super().run()

    def subscribe(self, event_cls, listener_cls):
        super().subscribe(event_cls, listener_cls(self) if issubclass(listener_cls, EventListener) else listener_cls())

class KeywordQueryEventListener(EventListener):
    def __init__(self, extension):
        self.extension = extension

    def on_event(self, event, extension):
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        start_time = time.time()
        loc_lang = 'en'  # Always English only
        loc = LOCALES.get(loc_lang, LOCALES['en'])

        try:
            api_key = extension.preferences['api_key']
            dalle_key = extension.preferences.get('dalle_api_key', '')
            temperature = float(extension.preferences['temperature'])
            system_prompt = extension.preferences['system_prompt']
            wrap_len = int(extension.preferences['line_wrap']) if extension.preferences['line_wrap'].isdigit() else 0
            enable_wrapping = extension.preferences.get('enable_wrapping', 'True').lower() == 'true'
            model = extension.preferences['model']
            log_directory = extension.preferences.get('log_directory', '').strip() or os.path.expanduser('~')
            logging_level = extension.preferences.get('logging_level', 'INFO').upper()
            theme = extension.preferences.get('theme', 'light')
            logger.setLevel(getattr(logging, logging_level, logging.INFO))
        except Exception as err:
            logger.error('Failed to parse preferences: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Failed to parse preferences',
                                    description=str(err),
                                    on_enter=CopyToClipboardAction(str(err)))
            ])

        if GPTExtension.api_call_count > 50:
            warning = "Quota warning: Exceeded 50 calls this session."
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Quota Exceeded',
                                    description=warning,
                                    on_enter=CopyToClipboardAction(warning))
            ])

        search_term = event.get_argument() or ''
        logger.info('The search term is: %s', search_term)

        # Special commands
        if search_term.lower() == 'clear history':
            self.extension.conversation_history = []
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['clear_success'],
                                    description='',
                                    on_enter=DoNothingAction())
            ])
        elif search_term.lower() == 'view history':
            history_preview = '\n'.join(
                [f"User: {ex['user'][:50]}... AI: {ex['ai'][:50]}..." for ex in self.extension.conversation_history[-5:]]
            ) or loc['no_history']
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Recent Conversation History',
                                    description=history_preview,
                                    on_enter=CopyToClipboardAction(history_preview))
            ])
        elif search_term.lower().startswith('generate image'):
            if not dalle_key:
                return RenderResultListAction([
                    ExtensionResultItem(icon=EXTENSION_ICON,
                                        name='Image generation requires DALL-E API key',
                                        description='Set in preferences',
                                        on_enter=DoNothingAction())
                ])
            prompt = search_term[14:].strip()  # After "generate image "
            image_url = generate_image(prompt, dalle_key, theme)
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['image_generated'],
                                    description=image_url,
                                    on_enter=CopyToClipboardAction(image_url))
            ])
        elif search_term.lower() == 'export full log':
            if not self.extension.conversation_history:
                return RenderResultListAction([
                    ExtensionResultItem(icon=EXTENSION_ICON,
                                        name=loc['no_history_export'],
                                        on_enter=DoNothingAction())
                ])
            log_content = create_log_md(self.extension.conversation_history, model, system_prompt, temperature, '',
                                        '', wrap_len, endpoint, time.time() - start_time, lang=loc_lang)
            filepath = save_log(log_directory, log_content)
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['export_success'],
                                    description=f'Path: {filepath}',
                                    on_enter=CopyToClipboardAction(filepath))
            ])

        if not search_term:
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['blank_prompt'],
                                    on_enter=DoNothingAction())
            ])

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        for exchange in self.extension.conversation_history:
            messages.append({"role": "user", "content": exchange['user']})
            messages.append({"role": "assistant", "content": exchange['ai']})
        messages.append({"role": "user", "content": search_term})

        headers = {'content-type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        body = {"messages": messages, "temperature": temperature, "model": model}

        retries = 0
        max_retries = 2
        response = None
        while retries <= max_retries:
            try:
                response = requests.post(endpoint, headers=headers, data=json.dumps(body), timeout=15)
                if response.status_code == 200:
                    break
            except Exception as err:
                logger.warning(f'Request failed (attempt {retries + 1}): {err}')
                retries += 1
                time.sleep(1)
            else:
                retries += 1
                time.sleep(1)

        if not response or response.status_code != 200:
            error_msg = f'Request failed after {max_retries} retries: {response.status_code if response else "No response"}'
            log_content = create_log_md(self.extension.conversation_history, model, system_prompt, temperature,
                                        search_term, '', wrap_len, endpoint, time.time() - start_time, error_msg, loc_lang)
            save_log(log_directory, log_content)
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['request_failed'],
                                    description=error_msg,
                                    on_enter=CopyToClipboardAction(error_msg))
            ])

        try:
            response_data = response.json()
            ai_response = response_data['choices'][0]['message']['content']
            wrapped_response = wrap_text(ai_response, wrap_len, theme) if enable_wrapping else ai_response
            self.extension.conversation_history.append({'user': search_term, 'ai': ai_response})
            GPTExtension.api_call_count += 1

            log_content = create_log_md(self.extension.conversation_history, model, system_prompt, temperature,
                                        search_term, wrapped_response, wrap_len, endpoint, time.time() - start_time, lang=loc_lang)
            filepath = save_log(log_directory, log_content)
            logger.info(f'Log saved to: {filepath}')

            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=f'Response from {model.split("/")[-1]}',
                                    description=wrapped_response[:200] + ('...' if len(wrapped_response) > 200 else ''),
                                    on_enter=CopyToClipboardAction(wrapped_response))
            ])
        except Exception as err:
            error_msg = f'Failed to parse response: {str(err)}'
            log_content = create_log_md(self.extension.conversation_history, model, system_prompt, temperature,
                                        search_term, '', wrap_len, endpoint, time.time() - start_time, error_msg, loc_lang)
            save_log(log_directory, log_content)
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name=loc['parse_error'],
                                    description=error_msg,
                                    on_enter=CopyToClipboardAction(error_msg))
            ])

if __name__ == '__main__':
    GPTExtension().run()