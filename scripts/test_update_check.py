"""
更新检查功能测试脚本
"""
import requests
import json

# 测试配置
API_BASE_URL = "http://localhost:8000"
TEST_VERSION = "1.0.0"
TEST_PLATFORM = "web"

def test_update_check():
    """测试更新检查功能"""
    print("🧪 开始测试更新检查功能...")
    
    # 1. 测试更新检查API (GET方式 - 最简单)
    print("\n1. 测试更新检查API (GET)")
    try:
        params = {
            "client_version": TEST_VERSION,
            "client_platform": TEST_PLATFORM,
            "user_agent": "TestAgent/1.0"
        }
        
        response = requests.get(
            f"{API_BASE_URL}/update/check",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET更新检查成功: {data}")
        else:
            print(f"❌ GET更新检查失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ GET更新检查异常: {e}")
    
    # 2. 测试更新检查API (POST方式)
    print("\n2. 测试更新检查API (POST)")
    try:
        response = requests.post(
            f"{API_BASE_URL}/update/check",
            json={
                "client_version": TEST_VERSION,
                "client_platform": TEST_PLATFORM,
                "user_agent": "TestAgent/1.0"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ POST更新检查成功: {data}")
        else:
            print(f"❌ POST更新检查失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ POST更新检查异常: {e}")
    
    # 3. 测试获取最新版本
    print("\n3. 测试获取最新版本")
    try:
        response = requests.get(
            f"{API_BASE_URL}/update/latest",
            params={"platform": TEST_PLATFORM},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取最新版本成功: {data}")
        else:
            print(f"❌ 获取最新版本失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 获取最新版本异常: {e}")
    
    # 4. 测试更新服务状态
    print("\n4. 测试更新服务状态")
    try:
        response = requests.get(
            f"{API_BASE_URL}/update/status",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务状态正常: {data}")
        else:
            print(f"❌ 服务状态异常: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 服务状态检查异常: {e}")

def main():
    """主测试函数"""
    print("🚀 更新检查功能测试")
    print("=" * 50)
    
    # 检查API服务是否运行
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API服务运行正常")
        else:
            print("❌ API服务异常")
            return
    except Exception as e:
        print(f"❌ 无法连接到API服务: {e}")
        print("请确保后端服务正在运行")
        return
    
    # 运行测试
    test_update_check()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成！")
    print("\n📝 前端调用示例:")
    print("1. 简单GET调用:")
    print(f"   fetch('{API_BASE_URL}/update/check?client_version=1.0.0&client_platform=web')")
    print("\n2. POST调用:")
    print(f"   fetch('{API_BASE_URL}/update/check', {{")
    print("     method: 'POST',")
    print("     headers: {'Content-Type': 'application/json'},")
    print("     body: JSON.stringify({client_version: '1.0.0', client_platform: 'web'})")
    print("   })")

if __name__ == "__main__":
    main()
