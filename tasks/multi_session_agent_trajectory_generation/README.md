# multi_session_agent_trajectory_generation

Converts persona timelines into multi-session user-agent trajectories. The smoke path uses a deterministic offline client; future LLM providers are selected through environment variables.

Offline demo:

```powershell
python tasks/persona_life_event_simulation/scripts/run_demo.py
python tasks/multi_session_agent_trajectory_generation/scripts/run_demo.py
```

Inputs:

- `examples/generated/persona_life_event_simulation/personas.jsonl`
- `configs/trajectory_generation.yaml`

Outputs:

- `examples/generated/multi_session_agent_trajectory_generation/trajectories.jsonl`

Optional LLM path: copy `.env.example` to `.env`, set `ULB_LLM_PROVIDER`, add provider keys, and replace the placeholder client implementation with provider calls while preserving the `LLMClient` protocol.

