#!/usr/bin/env python3
"""
AIOS-NP 安装脚本
用于安装Cerebrum SDK和配置环境
"""

import subprocess
import sys
import yaml
import os
from pathlib import Path

def get_user_input(prompt, default=""):
    """获取用户输入"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"{prompt}: ").strip()

def check_uv_installed():
    """检查uv是否已安装"""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ UV已安装: {result.stdout.strip()}")
            return True
        else:
            return False
    except FileNotFoundError:
        return False

def install_uv():
    """安装uv包管理器"""
    print("📦 安装UV包管理器...")
    try:
        result = subprocess.run([
            "curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"
        ], shell=True, check=True, capture_output=True, text=True)
        print("✅ UV安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ UV安装失败: {e}")
        return False

def install_dependencies_with_uv(requirements_file, description):
    """使用uv安装依赖"""
    print(f"\n📦 {description}...")
    print(f"   使用文件: {requirements_file}")
    
    if not Path(requirements_file).exists():
        print(f"   ⚠️  文件不存在: {requirements_file}")
        return False
    
    try:
        # 使用uv pip install安装依赖，使用清华镜像源
        cmd = ["uv", "pip", "install", "-r", requirements_file, "--default-index", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        print(f"   执行命令: {' '.join(cmd)}")
        print(f"   使用镜像源: https://pypi.tuna.tsinghua.edu.cn/simple")
        
        # 不使用capture_output，让用户能看到实时安装过程
        result = subprocess.run(
            cmd, 
            check=True, 
            timeout=600  # 10分钟超时
        )
        
        print(f"   ✅ {description}安装成功")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"   ⏰ {description}安装超时")
        return False
    except subprocess.CalledProcessError as e:
        print(f"   ❌ {description}安装失败: {e}")
        return False
    except Exception as e:
        print(f"   ❌ {description}安装异常: {e}")
        return False

def install_aios_dependencies():
    """安装AIOS依赖"""
    print("\n🔧 安装AIOS依赖...")
    
    # 询问用户选择GPU或CPU版本
    print("\n💻 选择依赖版本:")
    choice = get_user_input("选择版本 (gpu/cpu)", "gpu")
    
    if choice.lower() == "gpu":
        requirements_file = "aios/requirements-cuda.txt"
        description = "AIOS GPU依赖 (CUDA版本)"
    else:
        requirements_file = "aios/requirements.txt"
        description = "AIOS CPU依赖"
    
    return install_dependencies_with_uv(requirements_file, description)

def install_cerebrum_dependencies():
    """安装Cerebrum依赖"""
    print("\n🔧 安装Cerebrum依赖...")
    
    requirements_file = "cerebrum/requirements.txt"
    description = "Cerebrum基础依赖"
    
    return install_dependencies_with_uv(requirements_file, description)

def install_cerebrum_sdk():
    """安装Cerebrum SDK"""
    print("\n🔧 安装Cerebrum SDK...")
    
    # 切换到cerebrum目录
    cerebrum_dir = Path("cerebrum")
    if not cerebrum_dir.exists():
        print("❌ Cerebrum目录不存在")
        return False
    
    try:
        print("   使用pyproject.toml安装...")
        cmd = ["uv", "pip", "install", "-e", ".", "--default-index", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        
        print(f"   执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, 
            cwd=cerebrum_dir, 
            check=True,
            timeout=300
        )
        
        print("✅ Cerebrum SDK 安装成功")
        
        # 验证安装
        print("   验证安装...")
        try:
            import cerebrum
            print(f"   ✅ 包名: {cerebrum.__name__}")
            print(f"   ✅ 版本: {getattr(cerebrum, '__version__', 'unknown')}")
            print(f"   ✅ 路径: {cerebrum.__file__}")
        except ImportError as e:
            print(f"   ⚠️  导入验证失败: {e}")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("⏰ Cerebrum SDK 安装超时")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Cerebrum SDK 安装失败: {e}")
        return False

def setup_global_paths():
    """设置全局Python路径，让所有agents都能直接导入cerebrum"""
    print("\n🔧 设置全局Python路径...")
    
    try:
        # 获取项目根目录
        project_root = Path.cwd().absolute()
        cerebrum_path = project_root / "cerebrum"
        
        # 设置PYTHONPATH环境变量
        current_pythonpath = os.environ.get('PYTHONPATH', '')
        new_paths = [str(project_root), str(cerebrum_path)]
        
        if current_pythonpath:
            existing_paths = current_pythonpath.split(os.pathsep)
            new_paths.extend([p for p in existing_paths if p not in new_paths])
        
        new_pythonpath = os.pathsep.join(new_paths)
        os.environ['PYTHONPATH'] = new_pythonpath
        
        print(f"   ✅ 项目根目录: {project_root}")
        print(f"   ✅ cerebrum路径: {cerebrum_path}")
        print(f"   ✅ PYTHONPATH已更新")
        
        # 创建.pth文件，让路径设置永久生效
        site_packages = None
        try:
            import site
            site_packages = site.getsitepackages()[0] if site.getsitepackages() else None
        except:
            pass
        
        if site_packages:
            pth_file = Path(site_packages) / "aios-np.pth"
            try:
                with open(pth_file, 'w') as f:
                    f.write(f"{project_root}\n{cerebrum_path}\n")
                print(f"   ✅ 永久路径文件已创建: {pth_file}")
            except Exception as e:
                print(f"   ⚠️  永久路径文件创建失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 设置全局路径失败: {e}")
        return False

def configure_aios_config():
    """配置AIOS配置文件"""
    print("\n🔧 配置AIOS设置...")
    
    config_file = Path("aios/config/config.yaml")
    if not config_file.exists():
        print(f"❌ AIOS配置文件不存在: {config_file}")
        return None
    
    # 读取现有配置
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 读取AIOS配置文件失败: {e}")
        return None
    
    # 获取用户输入
    print("\n📝 模型配置:")
    model_name = get_user_input("模型名称", "QwQ-32B")
    backend = get_user_input("后端类型 (vllm/ollama/openai/gemini/anthropic/huggingface)", "vllm")
    
    # 询问是否替换所有模型
    replace_all = get_user_input("是否替换所有现有模型配置？(y/n)", "y")
    replace_all = replace_all.lower() in ['y', 'yes', '是', '1', 'true']
    
    # 根据后端类型配置相应的参数
    if backend == "vllm":
        vllm_host = get_user_input("vLLM服务器主机地址", "localhost")
        vllm_port = get_user_input("vLLM服务器端口", "8000")
        hostname = f"http://{vllm_host}:{vllm_port}/v1"
        print(f"   💡 vLLM提示: 请确保vLLM服务正在运行，例如: python -m vllm.entrypoints.openai.api_server --model your_path/QwQ-32B --served-model-name QwQ-32B  --tensor_parallel_size 4 --gpu-memory-utilization 0.8  --enable-auto-tool-choice --tool-call-parser hermes --max-model-len 26288 --enforce-eager --disable-custom-all-reduce")
    elif backend == "ollama":
        hostname = get_user_input("Ollama服务器地址", "http://localhost:11434")
        print(f"   💡 Ollama提示: 请确保Ollama服务正在运行，例如: ollama serve")
    elif backend == "openai":
        api_key = get_user_input("OpenAI API密钥", "")
        if api_key:
            print(f"   ✅ OpenAI API密钥已配置")
        hostname = "https://api.openai.com/v1"
    elif backend == "gemini":
        api_key = get_user_input("Google Gemini API密钥", "")
        if api_key:
            print(f"   ✅ Gemini API密钥已配置")
        hostname = "https://generativelanguage.googleapis.com"
    elif backend == "anthropic":
        api_key = get_user_input("Anthropic Claude API密钥", "")
        if api_key:
            print(f"   ✅ Claude API密钥已配置")
        hostname = "https://api.anthropic.com"
    elif backend == "huggingface":
        api_key = get_user_input("HuggingFace Auth Token", "")
        cache_dir = get_user_input("HuggingFace缓存目录", "~/.cache/huggingface")
        if api_key:
            print(f"   ✅ HuggingFace Auth Token已配置")
        hostname = "https://huggingface.co"
    else:
        hostname = get_user_input("服务器地址", "http://localhost:8000")
    
    print("\n🌐 AIOS内核服务器配置:")
    server_host = get_user_input("内核主机地址", "localhost")
    server_port = get_user_input("内核端口", "8001")
    
    # 更新配置
    if 'llms' not in config:
        config['llms'] = {}
    if 'models' not in config['llms']:
        config['llms']['models'] = []
    
    # 添加或更新模型配置
    new_model = {
        'name': model_name,
        'backend': backend,
        'hostname': hostname
    }
    
    # 根据后端类型添加特定配置
    if backend == "openai" and 'api_key' in locals():
        new_model['api_key'] = api_key
    elif backend == "gemini" and 'api_key' in locals():
        new_model['api_key'] = api_key
    elif backend == "anthropic" and 'api_key' in locals():
        new_model['api_key'] = api_key
    elif backend == "huggingface" and 'api_key' in locals():
        new_model['auth_token'] = api_key
        if 'cache_dir' in locals():
            new_model['cache_dir'] = cache_dir
    
    # 根据用户选择处理模型配置
    if replace_all:
        # 替换所有模型配置
        config['llms']['models'] = [new_model]
        print(f"   🔄 替换所有模型配置，新模型: {model_name}")
    else:
        # 检查是否已存在相同名称的模型，如果存在则更新，否则添加
        model_exists = False
        for i, model in enumerate(config['llms']['models']):
            if model.get('name') == model_name:
                config['llms']['models'][i] = new_model
                model_exists = True
                break
        
        if not model_exists:
            config['llms']['models'].append(new_model)
            print(f"   ➕ 添加新模型: {model_name}")
        else:
            print(f"   🔄 更新现有模型: {model_name}")
    
    # 更新服务器配置
    if 'server' not in config:
        config['server'] = {}
    config['server']['host'] = server_host
    config['server']['port'] = int(server_port)
    
    # 更新API密钥配置（如果用户输入了的话）
    if 'api_keys' not in config:
        config['api_keys'] = {}
    
    if backend == "openai" and 'api_key' in locals() and api_key:
        config['api_keys']['openai'] = api_key
    elif backend == "gemini" and 'api_key' in locals() and api_key:
        config['api_keys']['gemini'] = api_key
    elif backend == "anthropic" and 'api_key' in locals() and api_key:
        config['api_keys']['anthropic'] = api_key
    elif backend == "huggingface" and 'api_key' in locals() and api_key:
        if 'huggingface' not in config['api_keys']:
            config['api_keys']['huggingface'] = {}
        config['api_keys']['huggingface']['auth_token'] = api_key
        if 'cache_dir' in locals() and cache_dir:
            config['api_keys']['huggingface']['cache_dir'] = cache_dir
    
    # 保存配置
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✅ AIOS配置已更新: {config_file}")
        
        # 返回服务器配置信息，供Cerebrum配置使用
        return {
            'host': server_host,
            'port': int(server_port)
        }
    except Exception as e:
        print(f"❌ 保存AIOS配置失败: {e}")
        return None

def configure_cerebrum_config(aios_server_config):
    """配置Cerebrum配置文件，使用AIOS服务器配置"""
    print("\n🔧 配置Cerebrum设置...")
    
    if not aios_server_config:
        print("❌ 无法获取AIOS服务器配置")
        return False
    
    config_file = Path("cerebrum/config/config.yaml")
    if not config_file.exists():
        print(f"❌ Cerebrum配置文件不存在: {config_file}")
        return False
    
    # 读取现有配置
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 读取Cerebrum配置文件失败: {e}")
        return False
    
    # 自动使用AIOS服务器配置
    kernel_host = aios_server_config['host']
    kernel_port = aios_server_config['port']
    
    print(f"\n🔗 AIOS内核连接配置 (自动同步):")
    print(f"  内核地址: {kernel_host}:{kernel_port}")
    
    # 更新配置
    if 'kernel' not in config:
        config['kernel'] = {}
    
    config['kernel']['base_url'] = f"http://{kernel_host}:{kernel_port}"
    config['kernel']['timeout'] = 30  # 使用默认超时时间
    
    # 保存配置
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✅ Cerebrum配置已更新: {config_file}")
        print(f"  自动连接到AIOS内核: http://{kernel_host}:{kernel_port}")
        return True
    except Exception as e:
        print(f"❌ 保存Cerebrum配置失败: {e}")
        return False



def show_config_summary():
    """显示配置摘要"""
    print("\n" + "=" * 60)
    print("📋 配置摘要")
    print("=" * 60)
    
    print("\n🔧 AIOS配置位置:")
    print("  - 模型配置: AIOS-NP/aios/config/config.yaml")
    print("  - 服务器配置: AIOS-NP/aios/config/config.yaml")
    
    print("\n🔧 Cerebrum配置位置:")
    print("  - 内核连接: AIOS-NP/cerebrum/config/config.yaml")
    
    print("\n🔧 Python环境配置:")
    print("  - 项目根目录: /data/llm/AIOS-NP")
    print("  - ✅ cerebrum包已正确安装")
    print("  - ✅ 全局路径已设置，agents可直接导入cerebrum")
    print("  - ✅ 无需在每个脚本中设置路径")
    
    print("\n📝 如需修改配置，请编辑上述文件")
    print("=" * 60)

def main():
    """主安装流程"""
    print("🚀 AIOS-NP 安装开始...")
    print("=" * 50)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    
    print(f"✅ Python版本: {sys.version}")
    
    # 检查PyYAML
    try:
        import yaml
    except ImportError:
        print("📦 安装PyYAML...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "PyYAML"], check=True)
            print("✅ PyYAML 安装成功")
        except subprocess.CalledProcessError:
            print("❌ PyYAML 安装失败")
            sys.exit(1)
    
    # 检查并安装uv
    if not check_uv_installed():
        print("📦 UV包管理器未安装，正在安装...")
        if not install_uv():
            print("❌ UV安装失败，请手动安装后重试")
            print("   安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh")
            sys.exit(1)
    
    # 安装AIOS依赖
    if not install_aios_dependencies():
        print("❌ AIOS依赖安装失败")
        sys.exit(1)
    
    # 安装Cerebrum依赖
    if not install_cerebrum_dependencies():
        print("❌ Cerebrum依赖安装失败")
        sys.exit(1)
    
    # 配置AIOS
    aios_server_config = configure_aios_config()
    if not aios_server_config:
        print("❌ AIOS配置失败")
        sys.exit(1)
    
    # 配置Cerebrum（自动使用AIOS服务器配置）
    if not configure_cerebrum_config(aios_server_config):
        print("❌ Cerebrum配置失败")
        sys.exit(1)
    
    # 安装Cerebrum SDK
    if not install_cerebrum_sdk():
        print("❌ Cerebrum SDK安装失败")
        sys.exit(1)
    
    # 设置全局Python路径
    if not setup_global_paths():
        print("❌ 设置全局路径失败")
        sys.exit(1)
    
    # 显示配置摘要
    show_config_summary()
    
    print("\n🎉 AIOS-NP 安装完成！")
    print("\n📋 下一步:")
    print("1. 确认配置是否正确, 本地大模型是否在运行, 在线API是否正确")
    print("2. 请确保启动的大模型具有工具调用功能! ")
    print("3. 启动AIOS内核服务, bash runtime/launch_kernel.sh")
    print("4. 另开终端, 运行runtime里的脚本, 开始使用AIOS-NP！")
    print("=" * 50)

if __name__ == "__main__":
    main() 