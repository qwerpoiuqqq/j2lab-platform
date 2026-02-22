# superap.io 다중 세션 테스트 결과

## 테스트 일시

2026-02-04

## 테스트 목적

1. 동일 계정 다중 세션 허용 여부 확인
2. 다른 계정 병렬 로그인 가능 여부 확인

## 테스트 환경

- Playwright Chromium (headless=False)
- 스텔스 모드 활성화
- 독립 BrowserContext 사용

---

## 테스트 1: 동일 계정 다중 세션

### 테스트 시나리오

```python
await controller.login("worker1", "트래픽 제이투랩", "1234")
await controller.login("worker2", "트래픽 제이투랩", "1234")

status1 = await controller.check_login_status("worker1")
status2 = await controller.check_login_status("worker2")
```

### 결과

| 항목 | 값 |
|------|-----|
| 워커1 로그인 | 성공 |
| 워커2 로그인 | 성공 |
| 워커1 상태 유지 | 로그인됨 |
| 워커2 상태 유지 | 로그인됨 |
| 활성 컨텍스트 수 | 2 |

### 결론

**동일 계정 다중 세션: 가능**

superap.io는 동일 계정으로 여러 브라우저 세션을 동시에 허용합니다.

---

## 테스트 2: 다른 계정 병렬 로그인

### 테스트 시나리오

```python
await controller.login("account_a", "트래픽 제이투랩", "1234")
await controller.login("account_b", "월보장 일류기획", "1234")

status_a = await controller.check_login_status("account_a")
status_b = await controller.check_login_status("account_b")
```

### 결과

| 항목 | 값 |
|------|-----|
| 계정 A 로그인 | 성공 |
| 계정 B 로그인 | 성공 |
| 계정 A 상태 유지 | 로그인됨 |
| 계정 B 상태 유지 | 로그인됨 |
| 활성 컨텍스트 수 | 2 |

### 결론

**다른 계정 병렬 로그인: 가능**

서로 다른 계정으로 동시에 로그인하여 작업할 수 있습니다.

---

## 최종 결론

| 테스트 | 결과 |
|--------|------|
| 동일 계정 다중 세션 | **가능** |
| 다른 계정 병렬 로그인 | **가능** |

## 아키텍처 영향

### 병렬 처리 가능 범위

```
┌─────────────────────────────────────────────────────────────┐
│                    SuperapController                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Context 1     │   Context 2     │   Context 3             │
│   (worker1)     │   (worker2)     │   (worker3)             │
│   계정A 세션    │   계정A 세션    │   계정B 세션            │
├─────────────────┼─────────────────┼─────────────────────────┤
│   업체1 세팅    │   업체2 세팅    │   업체3 세팅            │
│   (병렬)        │   (병렬)        │   (병렬)                │
└─────────────────┴─────────────────┴─────────────────────────┘
```

### 권장 사용 방식

```python
# 계정 A로 10개 업체 병렬 세팅
workers = []
for i in range(10):
    worker_id = f"account_a_worker{i}"
    await controller.login(worker_id, "트래픽 제이투랩", "1234")
    workers.append(worker_id)

# 병렬 처리
await asyncio.gather(*[
    setup_business(controller, workers[i], businesses[i])
    for i in range(10)
])
```

### 주의사항

1. **리소스 제한**: 너무 많은 컨텍스트는 메모리 부담
2. **서버 부하**: 동시 요청이 많으면 rate limit 가능성
3. **권장 동시 세션**: 3~5개로 시작, 문제 없으면 점진적 증가

## 스크린샷

- `scripts/multi_session_worker1.png` - 동일 계정 워커1
- `scripts/multi_session_worker2.png` - 동일 계정 워커2
- `scripts/multi_session_account_a.png` - 계정 A
- `scripts/multi_session_account_b.png` - 계정 B
