#!/usr/bin/env python3
"""
测试带认证的API调用
"""
import asyncio
import json
import uuid
import httpx

USERNAME = f"test_user_{uuid.uuid4().hex[:8]}"
PASSWORD = "Test1234"
BASE_URL = "http://118.24.67.10:8000"

async def test_api_with_auth():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print(f"🔐 创建测试用户: {USERNAME}")
        
        # 1. 注册用户
        try:
            await client.post("/auth/register", json={"username": USERNAME, "password": PASSWORD})
            print("✅ 用户注册成功")
        except Exception as e:
            print(f"⚠️ 用户可能已存在: {e}")
        
        # 2. 登录获取token
        print("🔑 正在登录...")
        resp = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        resp.raise_for_status()
        token = resp.json().get("access_token")
        print(f"✅ 登录成功，获得token: {token[:20]}...")
        
        # 3. 测试需要认证的API
        headers = {"Authorization": f"Bearer {token}"}
        
        print("\n📊 测试文件统计API...")
        try:
            resp = await client.get("/files/stats", headers=headers)
            print(f"✅ 文件统计API: {resp.status_code}")
            print(f"   响应: {resp.json()}")
        except Exception as e:
            print(f"❌ 文件统计API失败: {e}")
        
        print("\n📁 测试文件列表API...")
        try:
            resp = await client.get("/files/list?page=1&page_size=10", headers=headers)
            print(f"✅ 文件列表API: {resp.status_code}")
            print(f"   响应: {resp.json()}")
        except Exception as e:
            print(f"❌ 文件列表API失败: {e}")
        
        print("\n💾 测试配额API...")
        try:
            resp = await client.get("/quota/today", headers=headers)
            print(f"✅ 配额API: {resp.status_code}")
            print(f"   响应: {resp.json()}")
        except Exception as e:
            print(f"❌ 配额API失败: {e}")
        
        print("\n🔄 测试更新检查API (无需认证)...")
        try:
            resp = await client.get("/update/check?client_version=1.0.0&client_platform=web")
            print(f"✅ 更新检查API: {resp.status_code}")
            data = resp.json()
            print(f"   发现更新: {data.get('has_update')}")
        except Exception as e:
            print(f"❌ 更新检查API失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_with_auth())
