# Typr QA matrix: 53 cases

The [QA index](../../tests.ipynb) and its case notebooks are the source for individual case evidence. This matrix distinguishes the November 22, 2026 local review from the November 21 historical baseline. Neither is a CI run of this delivery branch.

| Family | Verified | Partial | Pending | Manually accepted | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Functional | 29 | 0 | 0 | 0 | 29 |
| Integrity | 15 | 0 | 0 | 0 | 15 |
| Usability | 2 | 2 | 0 | 1 | 5 |
| Automation | 1 | 3 | 0 | 0 | 4 |
| **Local total** | **47** | **5** | **0** | **1** | **53** |

- **Verified** means an observed execution covered the scenario. **Partial** means only some criteria or layers were verified. **Pending** means no applicable run was identified. **Manually accepted** records acceptance, not an independently observed run.
- [TC-USAB-02](../../notebooks/usabilidad.ipynb#TC-USAB-02) remains partial: the original checklist and style guide are missing. NVDA and five human sessions are outside this delivery. Raw captures are not distributed.
- [TC-AUTO-02](../../notebooks/automatizacion.ipynb#TC-AUTO-02) remains partial and informational. The [partial local coverage union](../../notebooks/automatizacion.ipynb#cobertura-local-parcial) and the [backend service branch gate](coverage-baseline.md) have different scopes; neither is a global coverage figure. Live checks, artifact publication, and effective merge protection are unverified.

## Historical baseline

The historical inventory used the Master Test Plan (§§5.5–5.7) at [`4ea0151`](https://github.com/1Bnja/Typr/tree/4ea0151125e7268196a8ba78ce1dba823d32fb5d). These were the recorded statuses, not current gaps. Within each row, IDs use the family prefix shown; ranges are inclusive.

| Family | Verified | Partial | Pending | Manually accepted |
| --- | --- | --- | --- | --- |
| TC-FUNC | 01–06, 08–09, 11, 14, 17, 19, 21–22, 25–26, 28–29 | 07, 10, 12–13, 15–16, 18, 20, 23–24, 27 | — | — |
| RI | 02, 04, 09, 12, 15 | 01, 03, 06–08, 10–11, 13–14 | 05 | — |
| TC-USAB | — | — | — | 01–05 |
| TC-AUTO | 02–03 | 01, 04 | — | — |
| **Historical total** | **25** | **22** | **1** | **5** |

- **U —** [Historical backend run](https://github.com/1Bnja/Typr/actions/runs/44830544537): migrations and three `unittest` groups (107 text, 8 PostgreSQL integration, 116 general). No browser, Behave, or latency.
- **G, F, W —** [Historical PR #103 run](https://github.com/1Bnja/Typr/actions/runs/44826639378): G covers 34 Behave and 15 browser scenarios; F covers 46 Node tests, lint, frontend build, and Docker build; W covers isolated WebSocket latency (p95 16.2 ms, not a production figure).
- **D —** [Historical deployment](https://github.com/1Bnja/Typr/actions/runs/44830544676): a successful deployment is not proof that any check was required for merging or deploying.
