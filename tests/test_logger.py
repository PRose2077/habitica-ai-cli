"""测试日志系统和敏感数据过滤"""

import logging
import tempfile
from pathlib import Path

from habitica_forge.utils.logger import SensitiveDataFilter, setup_logger


def test_sensitive_data_filter():
    """测试敏感数据过滤器"""
    filter_ = SensitiveDataFilter()

    # 测试 API Key 过滤
    text1 = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
    result1 = filter_._redact(text1)
    assert "sk-1234567890" not in result1
    assert "[API_KEY_REDACTED]" in result1
    print(f"[PASS] API Key 过滤: {result1}")

    # 测试 Token 过滤
    text2 = 'token: "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"'
    result2 = filter_._redact(text2)
    assert "ghp_" not in result2
    assert "[TOKEN_REDACTED]" in result2
    print(f"[PASS] Token 过滤: {result2}")

    # 测试 UUID 过滤
    text3 = "user_id: 480ac1e2-1234-5678-9abc-def012345678"
    result3 = filter_._redact(text3)
    assert "480ac1e2" not in result3
    assert "[UUID_REDACTED]" in result3
    print(f"[PASS] UUID 过滤: {result3}")

    # 测试 Bearer token 过滤
    text4 = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    result4 = filter_._redact(text4)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result4
    assert "Bearer REDACTED" in result4
    print(f"[PASS] Bearer 过滤: {result4}")

    # 测试 x-api-user 和 x-api-key 过滤
    text5 = "x-api-user: abc123xyz"
    result5 = filter_._redact(text5)
    assert "abc123xyz" not in result5
    print(f"[PASS] x-api-user 过滤: {result5}")

    text6 = "x-api-key: secret-key-12345678"
    result6 = filter_._redact(text6)
    assert "secret-key-12345678" not in result6
    print(f"[PASS] x-api-key 过滤: {result6}")


def test_logger_writes_to_file():
    """测试日志写入文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = setup_logger(
            name="test_logger_file",
            level="DEBUG",
            log_file=log_file,
        )

        # 写入日志
        logger.info("Test info message")
        logger.debug("Test debug with api_key=sk-test123456789012345678901234")

        # 强制刷新并关闭处理器
        for handler in logger.handlers:
            handler.flush()
            handler.close()

        # 读取并验证
        content = log_file.read_text(encoding="utf-8")
        assert "Test info message" in content
        # 验证敏感数据被过滤
        assert "sk-test123456789012345678901234" not in content
        print(f"[PASS] 日志文件写入成功，敏感数据已过滤")
        print(f"日志内容:\n{content}")

        # 移除处理器以释放文件锁
        logger.handlers.clear()


if __name__ == "__main__":
    print("=== 测试敏感数据过滤器 ===")
    test_sensitive_data_filter()
    print("\n=== 测试日志文件写入 ===")
    test_logger_writes_to_file()
    print("\n所有测试通过！")