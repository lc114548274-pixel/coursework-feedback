"""修复本机误套 R1 模板的 Qwen3 权重；创建新别名，绝不覆盖来源模型或下载权重。"""
import argparse
import httpx

TARGET = 'coursework-qwen3:8b'
TEMPLATE = '''{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ range .Messages }}{{ if ne .Role "system" }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}{{ end }}<|im_start|>assistant
<think>

</think>

'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='deepseek-r1:latest')
    args = parser.parse_args()
    with httpx.Client(base_url='http://127.0.0.1:11434', timeout=60, trust_env=False) as client:
        metadata = client.post('/api/show', json={'model': args.source})
        metadata.raise_for_status()
        architecture = metadata.json().get('model_info', {}).get('general.architecture')
        if architecture != 'qwen3':
            raise SystemExit('来源架构不是 qwen3，拒绝套用此模板；请使用正确的 Qwen3 模型。')
        names = [m['name'] for m in client.get('/api/tags').json()['models']]
        if TARGET in names:
            previous = client.post('/api/show', json={'model': TARGET}).json()
            if TEMPLATE.strip() not in previous.get('modelfile', '') or previous.get('details', {}).get('parent_model') != args.source:
                raise SystemExit('同名模型不属于本脚本，拒绝覆盖。')
            if previous.get('template_source') != 'gguf_chat_template':
                print('Corrected model already exists; kept unchanged: ' + TARGET)
                return
        result = client.post('/api/create', json={'model': TARGET, 'from': args.source, 'stream': False,
            'template': TEMPLATE, 'parser': 'qwen3', 'parameters': {'stop': ['<|im_end|>', '<|endoftext|>'],
                                               'num_ctx': 8192, 'temperature': 0, 'repeat_penalty': 1.05}})
        result.raise_for_status()
        print('Created ' + TARGET + ': ' + result.text)
        verified = client.post('/api/show', json={'model': TARGET})
        verified.raise_for_status()
        if '<|im_start|>' not in verified.json()['template'] or verified.json().get('template_source') == 'gguf_chat_template':
            raise SystemExit('创建后仍未使用 Qwen3 ChatML 模板，请检查本机 Ollama 的 PARSER 支持；未覆盖原模型。')
        print('Verified Qwen3 ChatML template; original model preserved; no model download.')

if __name__ == '__main__':
    main()
