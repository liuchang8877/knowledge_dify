import requests

DIFY_API_URL = "http://localhost/v1/workflows/run"
API_KEY = "app-Ldb8XC7DRni6UMysWSmWrmGq"
WORKFLOW_ID = "b7a196d3-f730-4a2a-90fc-73cb2a46eaae"

def test_workflow(query: str, knowledge_id: str | None = None):
    payload = {
        "workflow_id": WORKFLOW_ID,
        "inputs": {"query": query},
        "user": "test-user"
    }
    if knowledge_id:
        payload["inputs"]["knowledge_id"] = knowledge_id

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(DIFY_API_URL, json=payload, headers=headers)
    print(f"\nTesting with knowledge_id: {knowledge_id}")
    print("Status Code:", response.status_code)
    print("Response:", response.json())

# 测试用例 1：动态传入 knowledge_id
test_workflow("Paris", "c80d5480-1820-4279-a18a-3eab3442e4a7")

# 测试用例 2：传入另一个 knowledge_id
#test_workflow("Tokyo", "4e490ab8f-1304-4a84-8b53-334e19d548d8")  # 替换为另一个有效 ID

# 测试用例 3：不传 knowledge_id
#test_workflow("What is the capital?")