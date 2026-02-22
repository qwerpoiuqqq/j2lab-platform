# superap.io 셀렉터 문서

## 개요

superap.io 로그인 자동화를 위한 CSS 셀렉터 문서입니다.

## 분석 일자

2026-02-04

## 테스트 URL

```
https://superap.io
```

## 로그인 페이지

### 1. 로그인 폼

#### 폼 셀렉터
```css
form[action="/j_spring_security_check"]
```

**HTML 구조:**
```html
<form action="/j_spring_security_check" method="POST">
  <input type="text" name="j_username" placeholder="ID">
  <input type="password" name="j_password" placeholder="Password">
  <button type="submit">Login</button>
</form>
```

### 2. 입력 필드

#### 아이디 입력
```css
input[name="j_username"]
```

| 속성 | 값 |
|------|-----|
| type | text |
| name | j_username |
| placeholder | ID |

#### 비밀번호 입력
```css
input[name="j_password"]
```

| 속성 | 값 |
|------|-----|
| type | password |
| name | j_password |
| placeholder | Password |

### 3. 버튼

#### 로그인 버튼
```css
button[type="submit"]
```

| 속성 | 값 |
|------|-----|
| type | submit |
| text | Login |

## 로그인 상태 판단

### 로그인 성공 조건
- 로그인 폼이 페이지에 존재하지 않음
- `form[action="/j_spring_security_check"]` 셀렉터로 요소를 찾을 수 없음

### 로그인 실패 조건
- 로그인 폼이 여전히 존재
- 에러 메시지 요소 표시

### 에러 메시지 셀렉터
```css
.error, .alert-danger, [class*="error"]
```

## 로그아웃

### 로그아웃 링크 (로그인 상태 확인용)
```css
a[href*="logout"]
```

## 사용 예시

### Python (Playwright)

```python
from app.services.superap import SuperapController

async with SuperapController(headless=True) as controller:
    # 로그인
    await controller.login(
        account_id="user1",
        username="myid",
        password="mypassword"
    )

    # 로그인 상태 확인
    is_logged_in = await controller.check_login_status("user1")
    print(f"Logged in: {is_logged_in}")
```

## 주의사항

### 1. Spring Security 기반

superap.io는 Spring Security를 사용합니다.
- 폼 action: `/j_spring_security_check`
- 필드명: `j_username`, `j_password`
- CSRF 토큰이 필요할 수 있음 (현재는 불필요)

### 2. 세션 관리

- 로그인 성공 시 세션 쿠키 발급
- Playwright 컨텍스트에 쿠키 자동 저장
- 컨텍스트를 유지하면 재로그인 불필요

### 3. 컨텍스트 분리

다중 계정 처리 시 각 계정별 독립 컨텍스트 사용:

```python
# 계정별 독립 컨텍스트
ctx1 = await controller.get_context("account1")
ctx2 = await controller.get_context("account2")
# ctx1과 ctx2는 별도의 세션/쿠키를 가짐
```

## 셀렉터 상수 위치

파일: `backend/app/services/superap.py`

```python
class SuperapController:
    SELECTORS = {
        "login_form": 'form[action="/j_spring_security_check"]',
        "username_input": 'input[name="j_username"]',
        "password_input": 'input[name="j_password"]',
        "login_button": 'button[type="submit"]',
        "logout_link": 'a[href*="logout"]',
        "error_message": '.error, .alert-danger, [class*="error"]',
    }
```

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-04 | 최초 작성 - 로그인 페이지 셀렉터 |
