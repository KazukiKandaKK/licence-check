import os, uuid, yaml, time, pathlib
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load configuration
cfg = yaml.safe_load(open('prompts/prompt_spec.yaml'))
out = pathlib.Path('generated')
out.mkdir(parents=True, exist_ok=True)

# Configuration for LLM providers
USE_LOCAL_LLM = os.getenv('USE_LOCAL_LLM', 'false').lower() == 'true'
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
LOCAL_MODEL_1 = os.getenv('LOCAL_MODEL_1', 'codellama:7b')
LOCAL_MODEL_2 = os.getenv('LOCAL_MODEL_2', 'deepseek-coder:6.7b')

def call_openai(prompt):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None

def call_claude(prompt):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4000,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude API error: {e}")
        return None

def call_ollama(prompt, model):
    """Call local Ollama API"""
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }
        
        response = requests.post(url, json=data, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        return result.get('response', '')
        
    except Exception as e:
        print(f"Ollama API error with model {model}: {e}")
        return None

# Generate code for each language
for lang in cfg['languages']:
    tmpl = cfg['instruction'].format(lang=lang)
    ext = {'python':'py','go':'go','typescript':'ts'}[lang]
    path = out / lang
    path.mkdir(exist_ok=True)
    
    if USE_LOCAL_LLM:
        print(f"Generating {cfg['repeat']} files for {lang} using local LLMs...")
        print(f"Using models: {LOCAL_MODEL_1} and {LOCAL_MODEL_2}")
    else:
        print(f"Generating {cfg['repeat']} files for {lang} using OpenAI/Claude APIs...")
    
    for i in range(cfg['repeat']):
        try:
            code = None
            model_used = "unknown"
            
            if USE_LOCAL_LLM:
                # Alternate between local models
                if i % 2 == 0:
                    code = call_ollama(tmpl, LOCAL_MODEL_1)
                    model_used = LOCAL_MODEL_1
                else:
                    code = call_ollama(tmpl, LOCAL_MODEL_2)
                    model_used = LOCAL_MODEL_2
            else:
                # Use cloud APIs
                if i % 2 == 0:
                    code = call_openai(tmpl)
                    model_used = "OpenAI"
                else:
                    code = call_claude(tmpl)
                    model_used = "Claude"
            
            if code and code.strip():
                # Save to file
                filename = f"{uuid.uuid4()}.{ext}"
                (path / filename).write_text(code)
                print(f"Generated {lang} file {i+1}/{cfg['repeat']} using {model_used}")
            else:
                print(f"Failed to generate {lang} file {i+1}/{cfg['repeat']} with {model_used}")
                continue
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"Error generating {lang} file {i+1}: {e}")
            continue

print("Code generation complete!")