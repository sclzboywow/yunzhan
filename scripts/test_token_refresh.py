#!/usr/bin/env python3
"""
测试JWT token刷新功能
"""
import asyncio
import json
import uuid
import httpx

USERNAME = f"test_refresh_{uuid.uuid4().hex[:8]}"
PASSWORD = "Test1234"
BASE_URL = "http://118.24.67.10:8000"

async def test_token_refresh():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        print(f"🔐 创建测试用户: {USERNAME}")
        
        # 1. 注册用户
        try:
            await client.post("/auth/register", json={"username": USERNAME, "password": PASSWORD})
            print("✅ 用户注册成功")
        except Exception as e:
            print(f"⚠️ 用户可能已存在: {e}")
        
        # 2. 登录获取token对
        print("🔑 正在登录...")
        resp = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        print(f"✅ 登录成功")
        print(f"   Access Token: {access_token[:30]}...")
        print(f"   Refresh Token: {refresh_token[:30]}...")
        
        # 3. 使用access token测试API
        print("\n📊 使用access token测试API...")
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = await client.get("/files/stats", headers=headers)
            print(f"✅ 文件统计API: {resp.status_code}")
        except Exception as e:
            print(f"❌ 文件统计API失败: {e}")
        
        # 4. 使用refresh token获取新的token对
        print("\n🔄 使用refresh token刷新...")
        try:
            resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
            resp.raise_for_status()
            new_token_data = resp.json()
            new_access_token = new_token_data.get("access_token")
            new_refresh_token = new_token_data.get("refresh_token")
            print(f"✅ Token刷新成功")
            print(f"   新 Access Token: {new_access_token[:30]}...")
            print(f"   新 Refresh Token: {new_refresh_token[:30]}...")
            
            # 5. 使用新的access token测试API
            print("\n📊 使用新access token测试API...")
            new_headers = {"Authorization": f"Bearer {new_access_token}"}
            try:
                resp = await client.get("/files/stats", headers=new_headers)
                print(f"✅ 新token文件统计API: {resp.status_code}")
                print(f"   响应: {resp.json()}")
            except Exception as e:
                print(f"❌ 新token文件统计API失败: {e}")
                
        except Exception as e:
            print(f"❌ Token刷新失败: {e}")
        
        # 6. 测试无效refresh token
        print("\n🚫 测试无效refresh token...")
        try:
            resp = await client.post("/auth/refresh", json={"refresh_token": "invalid_token"})
            print(f"❌ 应该失败但成功了: {resp.status_code}")
        except Exception as e:
            print(f"✅ 正确拒绝了无效token: {e}")

if __name__ == "__main__":
    asyncio.run(test_token_refresh())
