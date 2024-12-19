from flask import Flask, render_template, request, jsonify
import requests
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

LMSTUDIO_API_URL = "http://127.0.0.1:1234"
HISTORY_FILE = "chat_history.json"  # 本地历史记录文件

# 读取历史记录
def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception:
        return []

# 保存历史记录
def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

@app.route('/get_history', methods=['GET'])
def get_history():
    try:
        history = load_history()
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    try:
        timeout = data.get('timeout', 240)  # 默认值为240秒
        response = requests.post(
            f"{LMSTUDIO_API_URL}/v1/chat/completions",
            json=data,
            timeout=timeout # 增加到240秒
        )
        response.raise_for_status()
        result = response.json()
        
        # 保存对话历史
        history = load_history()
        history.append({
            'role': 'user',
            'content': data['messages'][-1]['content']
        })
        history.append({
            'role': 'assistant',
            'content': result['choices'][0]['message']['content']
        })
        save_history(history)
        
        return jsonify(result)
    except requests.Timeout:
        error_msg = "LM Studio响应超时(240秒)，这可能是因为：\n1. 模型正在处理复杂的请求\n2. 模型资源占用过高\n请稍后重试或尝试减少输入长度"
        return jsonify({"error": error_msg}), 500
    except requests.RequestException as e:
        error_msg = f"与LM Studio通信出错: {str(e)}\n请确保LM Studio正在运行且API服务可用"
        return jsonify({"error": error_msg}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_models', methods=['GET'])
def get_models():
    try:
        # 检查LM Studio服务是否运行
        response = requests.get(f"{LMSTUDIO_API_URL}/v1/models", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        # 添加更详细的错误信息
        error_msg = f"无法连接到LM Studio服务 ({str(e)}), 请确保LM Studio已启动且API服务运行在端口1234"
        return jsonify({"error": error_msg}), 500

@app.route('/v1/embeddings', methods=['POST'])
def embeddings():
    try:
        file = request.files.get('file')
        image = request.files.get('image')
        payload = json.loads(request.form.get('payload'))
        
        # 确保 messages 列表不为空
        if not payload.get('messages'):
            return jsonify({"error": "消息列表不能为空"}), 400

        # 处理文件
        if file:
            # 处理文件的代码...
            pass

        # 处理图片
        if image:
            import base64
            # 重置文件指针
            image.seek(0)
            image_content = base64.b64encode(image.read()).decode('utf-8')
            image_type = image.content_type.split('/')[-1]
            
            # 确保最后一条消息是用户输入
            last_message = payload['messages'][-1]
            if last_message['role'] == 'user':
                last_message['content'] = [
                    {
                        "type": "text",
                        "text": last_message['content']
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_type};base64,{image_content}"
                        }
                    }
                ]

        # 发送到 LM Studio
        response = requests.post(
            f"{LMSTUDIO_API_URL}/v1/chat/completions",
            json=payload,
            timeout=payload.get('timeout', 240)
        )
        response.raise_for_status()
        result = response.json()
        
        # 保存对话历史
        history = load_history()

        # 保存用户输入
        if len(payload['messages']) >= 2:
            history.append({
                'role': 'user',
                'content': payload['messages'][-2]['content']  # 用户输入
            })
        else:
            history.append({
                'role': 'user',
                'content': payload['messages'][-1]['content']  # 用户输入
            })

        # 如果有文件上传，添加文件信息
        if file:
            history.append({
                'role': 'user',
                'content': f"[上传文件内容]: {file.filename}"
            })

        # 如果有图片上传，添加图片信息
        if image:
            history.append({
                'role': 'user',
                'content': f"[上传图片]: {image.filename}"
            })

        # 保存助手回复
        history.append({
            'role': 'assistant',
            'content': result['choices'][0]['message']['content']
        })

        save_history(history)
        
        return jsonify(result)
    except requests.Timeout:
        error_msg = "LM Studio响应超时，请稍后重试或尝试减少输入长度"
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"处理请求时出错: {str(e)}"
        return jsonify({"error": error_msg}), 500

@app.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        # 清空历史记录文件
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8180)
