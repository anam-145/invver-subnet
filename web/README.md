# web

Anam145 Bittensor 보안 서브넷 제안 — 공개 데모 사이트.
Bitstarter 지원서의 "Files & media" 항목에 링크할 정적 페이지다.

의존성 없는 **순수 정적 사이트**다. 빌드 스텝도, 백엔드도, 환경변수도 없다.

---

## 구조

```
web/
├── index.html          구조 + i18n 키
├── assets/
│   ├── styles.css      디자인 토큰 + 레이아웃
│   └── app.js          i18n · STEP 1 정적 분석기 · STEP 3 트레이스
└── README.md
```

---

## 로컬 실행

```bash
python -m http.server 8080
# → http://localhost:8080
```

또는

```bash
npx serve .
```

`file://` 로 직접 열어도 동작한다 (외부 fetch가 없다).

---

## 배포

### Nginx

```nginx
server {
    listen 80;
    server_name demo.example.com;
    root /var/www/invariant-subnet;
    index index.html;

    location / { try_files $uri $uri/ =404; }
    location /assets/ { expires 7d; add_header Cache-Control "public"; }
}
```

```bash
sudo mkdir -p /var/www/invariant-subnet
sudo rsync -av --delete ./ /var/www/invariant-subnet/ --exclude .git --exclude README.md
sudo nginx -t && sudo systemctl reload nginx
```

### Caddy (HTTPS 자동)

```
demo.example.com {
    root * /var/www/invariant-subnet
    file_server
}
```

### Vercel / Netlify / Cloudflare Pages / GitHub Pages

빌드 명령 없음, 출력 디렉터리 `.` 로 두고 레포를 그대로 연결하면 된다.

---

## 언어

우측 상단 `KO / EN` 토글. URL 파라미터로도 고정된다:

```
https://demo.example.com/?lang=en
```

**Bitstarter 지원서에는 `?lang=en` 을 붙여서 제출하세요.** 심사자가 영어로 먼저 봅니다.

---

## 디자인 토큰

| 역할 | 값 |
|---|---|
| Primary | `#3182F6` |
| Background | `#F9FAFB` |
| Text | `#4E5968` |
| Title | `#191F28` |
| Border | `#E5E8EB` |
| Sub text | `#8B95A1` |
| Fill | `#F2F4F6` |
| Danger | `#F04452` |
| Success | `#00A661` |

폰트는 **Pretendard Variable** (dynamic subset, jsDelivr CDN).

### 폰트를 자체 호스팅하려면

외부 CDN 의존을 없애고 싶으면:

```bash
mkdir -p assets/fonts
curl -L -o assets/fonts/PretendardVariable.woff2 \
  https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2
```

`index.html` 의 CDN `<link>` 를 지우고 `assets/styles.css` 맨 위에 추가:

```css
@font-face {
  font-family: "Pretendard Variable";
  font-weight: 45 920;
  font-style: normal;
  font-display: swap;
  src: url("./fonts/PretendardVariable.woff2") format("woff2-variations");
}
```

---

## 내용을 고칠 때

- **문구**: `assets/app.js` 의 `I18N` 객체. `ko` / `en` 양쪽을 같이 고칠 것.
- **근거 표**: 같은 파일 `EVIDENCE`.
- **한계 목록**: 같은 파일 `LIMITS`.
- **참조 property DB**: `PROPERTIES` — `../generator/src/reference_db.json` 과 동기화 유지.
- **정적 분석기**: `extractSignals` / `detectCEI` — `../generator/src/retrieve.mjs` 의 포트다. 한쪽만 고치지 말 것.

### ⚠️ STEP 2 · 3 을 실행한 뒤에 반드시 갱신할 것

지금 페이지는 STEP 2·3 을 **"미실행"** 으로 정직하게 표시하고 있다.
`generator` 에서 실제로 돌린 뒤에는:

1. `I18N.*.s2.warn` / `s3.warn` 의 경고 문구를 실측 결과로 교체
2. `.state.pending` → `.state.live` 로 클래스 변경 (`index.html`)
3. `EVIDENCE` 의 마지막 두 행 상태를 `no` → `ok` 로 변경
4. STEP 2 섹션에 실제 생성된 invariant 출력 추가

**실행하지 않은 결과를 채워 넣지 말 것.** 기술 인터뷰에서 바로 드러난다.

---

## 관련

- 소스 저장소: `../generator`
- 대상 컨트랙트: [DeFiVulnLabs / ERC777-reentrancy.sol](https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol) (MIT)
- Trace2Inv (MIT) · PropertyGPT, NDSS 2025
