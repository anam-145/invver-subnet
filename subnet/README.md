# subnet — Python

마이너 / 밸리데이터 / 네트워크 모니터링.

## 상태

| 모듈 | 상태 | 설명 |
|---|---|---|
| `invariant_subnet/protocol.py` | ✅ 구현 | 마이너·밸리데이터가 주고받는 타입. 전부 frozen — 채점이 순수 함수여야 하므로 |
| `invariant_subnet/scoring.py` | ✅ 구현 · 테스트 18개 통과 | **채점 규칙.** 이 프로젝트의 핵심 주장이 여기 들어있다 |
| `invariant_subnet/monitor.py` | ◐ 일부 | 로컬 채점 기록 집계는 동작. 체인 조회는 `NotImplementedError` |
| `neurons/validator.py` | ⬜ 스켈레톤 | 루프 형태만. 미구현 함수는 전부 raise |
| `neurons/miner.py` | ⬜ 스켈레톤 | 동일 |

**미구현 함수는 그럴듯한 값을 돌려주지 않고 `NotImplementedError` 를 던진다.** 스켈레톤이 돌아가는 것처럼 보이는 게 제일 위험하다.

## 실행

의존성이 없다. Python 3.10+ 만 있으면 된다.

```bash
cd subnet
python -m unittest discover tests -v
```

```
Ran 18 tests in 0.002s
OK
```

## 채점 규칙이 보장하는 것

`scoring.py` 는 **순수 함수**다. 시계도, 난수도, 네트워크도, 모델 호출도 없다.
같은 `ExecutionResult` 와 같은 ledger 를 가진 두 밸리데이터는 **같은 숫자**를 낸다.

| 요소 | 규칙 |
|---|---|
| 심각도 | invariant 클래스에 붙어 있고, 타깃 공개 시점에 고정된다. 제출물마다 매기지 않는다 |
| 신규성 | `(target_id, invariant_id, 최소화된 state delta 해시)`. 같은 버그를 재발견하면 키가 같아서 최초 1명만 받는다 |
| 기지 익스플로잇 | 타깃 공개 전에 ledger 에 미리 심는다. 공개된 공격 재탕은 0점 |
| 최소성 | 호출 횟수. 짧을수록 가산, 상·하한이 있다. 논쟁 불가능한 정수값 |
| 처리 순서 | submission id 로 정렬. "누가 먼저였나"가 도착 순서에 의존하지 않는다 |

밸리데이터가 반대 결과를 내면 그건 **의견 차이가 아니라 버그이거나 배신**이다.
이 성질이 `monitor.validator_disagreement()` 가 존재하는 이유다.

## 모니터링

```python
from invariant_subnet.monitor import summarize_round, render_report, validator_disagreement

report = summarize_round("simplebank", scored_submissions)
print(render_report(report))

# 결정론적 채점이므로 정직한 밸리데이터 쌍의 차이는 정확히 0 이어야 한다
for a, b, delta in validator_disagreement(weights_by_validator):
    print(f"DIVERGENCE {a} vs {b}: {delta:.6f}")
```

`network_novelty_rate` 가 0 으로 수렴하면 마이너가 나빠진 게 아니라
**그 타깃의 invariant 집합이 소진된 것**이다 — 타깃 교체 신호로 쓴다.

## 다음 작업

1. `execute()` — `forge test` 를 셸아웃해서 실제 실행 결과를 만든다.
   하네스 자체는 이미 있다 → [`../generator/test/InvariantCheck.t.sol`](../generator/test/InvariantCheck.t.sol)
2. `search()` — 마이너 탐색. RL / LLM 후보 생성 / Echidna·Medusa 프로퍼티 퍼징
3. 체인 연동 — `bittensor` SDK, netuid 등록, metagraph 조회
4. 테스트넷 서브넷으로 전체 루프 실행

설계 배경: [`../docs/architecture.md`](../docs/architecture.md)
