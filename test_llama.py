"""
Script untuk test Llama 3.8b model via Ollama
"""

import requests
import sys


def test_ollama_connection():
    """Test koneksi ke Ollama service"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json()
            print("✅ Ollama Service RUNNING\n")
            print("📦 Available Models:")
            
            if 'models' in models:
                for model in models['models']:
                    print(f"   - {model['name']}")
            
            # Check if llama3:8b exists
            if 'models' in models:
                model_names = [m['name'] for m in models['models']]
                if any('llama3:8b' in name for name in model_names):
                    print("\n✅ Llama 3.8b model FOUND")
                    return True
                else:
                    print("\n❌ Llama 3.8b model NOT FOUND")
                    print("   Pull model dengan: ollama pull llama3:8b")
                    return False
            
        else:
            print(f"❌ Ollama error: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Tidak bisa connect ke Ollama service")
        print("\n⚠️  Pastikan:")
        print("   1. Ollama sudah terinstall")
        print("   2. Jalankan 'ollama serve' di terminal lain")
        print("   3. Default port adalah http://localhost:11434")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_llama_generation():
    """Test generate response dengan Llama"""
    print("\n" + "="*60)
    print("Testing Llama 3.8b Generation...")
    print("="*60 + "\n")
    
    try:
        prompt = "Jelaskan apa itu AI dalam 1 paragraf singkat."
        print(f"Prompt: {prompt}\n")
        print("Response from Llama 3.8b:")
        print("-" * 60)
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3:8b",
                "prompt": prompt,
                "stream": False,
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(result['response'])
            print("-" * 60)
            print("\n✅ Llama response SUCCESSFUL")
            return True
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timeout (Llama response terlalu lama)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("="*60)
    print("LLAMA 3.8B - Ollama Service Test")
    print("="*60 + "\n")
    
    # Test Ollama connection
    if not test_ollama_connection():
        print("\n⚠️  Silakan jalankan Ollama service terlebih dahulu:")
        print("   ollama serve")
        sys.exit(1)
    
    # Test generation
    if test_llama_generation():
        print("\n" + "="*60)
        print("✅ Semua test PASSED!")
        print("="*60)
    else:
        print("\n❌ Generation test FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
