# Perp DEX Delta-Neutral Bot Portfolio

가상자산 무기한선물 DEX에서 메이커 주문의 실제 체결량에 맞춰 반대 포지션을 구성하는 전략 코드의 공개 포트폴리오입니다. 기존 개발 프로젝트에서 주문·체결·헤지 처리 코드를 추리고, API 키 없이 실행할 수 있는 모의 거래소와 테스트를 덧붙였습니다.

**핵심 구현:** 비동기 API 경계, 체결 이벤트 처리, 실제 체결량 기준 헤지, 타임아웃 취소, 헤지 실패 시 잔여 노출 기록.


An inspectable slice of Junghwan Oh's private `2dex` development project, with an asynchronous maker-to-hedge order lifecycle and a deterministic offline exchange fixture. This snapshot is intended for technical review alongside a legal/technology career portfolio.

## Run locally

Python 3.10+; standard library only:

```sh
python -m portfolio_bot.demo
python -m unittest discover -s tests -v
```

The executable demo cannot place real orders. It contains no HTTP/WebSocket clients, signing code, exchange endpoints, credential readers or live-mode switch. `.env.example` documents that no credentials are necessary; the demo does not load it.

## What this shows

1. An async API boundary between strategy and exchange clients.
2. Maker placement, fill-event handling, fill timeout/cancellation.
3. An opposite-side hedge sized from the actual filled quantity.
4. Explicit signed imbalance recording when the hedge is rejected.
5. Decimal arithmetic for trading quantities.

The portfolio demonstrates a real source-code slice, not the entire production bot. `source_core.py` retains the actual `executeHedgeCycle` method from the private repository; `demo.py` supplies newly written offline fixtures instead of private live adapters. See `PROVENANCE.md` and `source-manifest.json` for exact source boundaries.

## Scope and limitations

The demo verifies order lifecycle behavior offline. Live adapters, point accounting, fees, funding, slippage and latency benchmarks are outside this snapshot.

The retained source method has known production limitations: a partial maker fill does not cancel the remaining maker quantity; terminal cancellation/rejection handling and late-fill reconciliation need stronger reconciliation; a successful hedge API response is assumed to be fully filled. These reconciliation cases require additional controls before any live integration.

No private Git history, trading logs, account identifiers, private configuration or production credentials are included.

## Attribution and license

The private project includes code derived from [your-quantguy/perp-dex-tools](https://github.com/your-quantguy/perp-dex-tools). The upstream **Non-Commercial License** is preserved in `LICENSE`. See `PROVENANCE.md` for the retained strategy code and the newly prepared demonstration harness. Commercial use requires separate permission from the copyright holder.
