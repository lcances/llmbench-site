---
title: "qwen3.5-4b on a 16 GB RTX 5060 Ti: 823 tokens per second for 16 users"
description: "qwen3.5-4b on a 16 GB RTX 5060 Ti: 823 tokens per second for 16 users"
tags: [ai, llm, benchmark, devops]
cover: "images/cover.png"
issue: "620ca8f6-006f-4b84-a09b-828f149dea6f"
---

qwen3.5-4b is a 4-billion-parameter language model in the small (<8B) class. On the test machine it generates text **21 times faster than you can read**, even with a 100-page book in the prompt. Models at that size can be interesting to run on mobile or at the edge.

## Straight to the Results

qwen3.5-4b is quick on an NVIDIA GeForce RTX 5060 Ti when prompts are short. Long prompts change that: the first word takes much longer to arrive, and generation slows down.

- Speed: **114 tokens per second** on a short prompt, dropping to **34 tokens per second** at the full 260k-token context.
- Waiting: **101 ms** to the first word on a short prompt, **6.5 s** on a 32k-token prompt.
- Electricity: **0.63 kWh per 1M generated tokens**, roughly **€0.16**.

The measurements below come from llama.cpp installed with its standard settings.

| Metric | 512 Context | 32k Context | Max Context (260k) |
| --- | --- | --- | --- |
| Prompt Processing (tok/s) | 5050 | 5031 | 1946 |
| TTFT | 101 ms | 6.5 s | 134.5 s |
| Generation (tok/s) | 114 | 88 | 34 |

## Which Program Should You Run It With?

The model ran under llama.cpp, Ollama and vLLM, each with its default settings.

| | llama.cpp | Ollama | vLLM |
| --- | --- | --- | --- |
| Writing speed, short prompt (tok/s) | 114 | 114 | 107 |
| Wait for first word, short prompt | 101 ms | 165 ms | 101 ms |
| Wait for first word, 32k prompt | 6.5 s | 7.3 s | 7.5 s |
| Longest context (tokens) | 262k | 262k | 256k |
| Start-up time | 1.03 s | 4.7 s | 48 s |
| Electricity (kWh per 1M tokens) | 0.63 | 0.65 | 0.52 |

For one person on one machine, llama.cpp is the straightforward choice. It ties Ollama on short-prompt speed, matches vLLM for the quickest first word, and starts in **1.03 s** against Ollama's 4.7 s and vLLM's **48 s**. Ollama runs at the same speed but takes longer to start and to answer.

vLLM earns its place on a shared machine. It uses the least electricity at **0.52 kWh per 1M tokens**, and its writing speed stays close to the other two on short prompts. The wait for the first word on a 32k prompt is 7.5 s, compared with 6.5 s for llama.cpp, a small gap next to its heavier setup and long start-up.

## Writing Speed as the Conversation Grows

![Writing speed vs context size](images/writing-speed-vs-context-size.png)

Decode speed stays close to the short-prompt figure until the context grows. llama.cpp drops from **114 tokens per second** at 512 tokens to 88 at 32k, giving up about a quarter of its pace, and Ollama matches it at both sizes. At the top, llama.cpp reaches **34 tokens per second** and Ollama 33, which makes the two interchangeable for raw throughput.

Past 32k, all three slow sharply. llama.cpp ends up about **3.4x** slower than at 512 tokens as the KV cache starts to eat into the card's memory. vLLM begins slightly behind at 107 tokens per second but holds up better; at the largest context it can manage, it still runs at **36 tokens per second**, about 6% ahead of llama.cpp and 7% ahead of Ollama. It has no figure at the full 262k size because it cannot hold that much context.

The wait for the first word at full context, about **135 s**, is mostly the time needed to process the 262k-token prompt at **1946 tokens per second**. The card spends 12 GB of its 16 GB on the KV cache, so the delay comes from reading the prompt rather than from slow generation.

## When Many People Use It at Once

![Total tokens produced per second vs simultaneous users](images/total-tokens-produced-per-second-vs-simultaneous-users.png)

A single vLLM server can serve **16 people at once**. Together they get **823 tokens per second**, compared with 103 tokens per second for one user alone, and each person still sees the first word after about 1210 ms. One budget computer can back a whole team or a small product, not just one user.

## The Test Bench

Every model in this series ran on the same machine, with the same **16 GB** GeForce RTX 5060 Ti, so the results can be compared directly. Any difference between models comes from the model itself rather than from a change in hardware.

| Component | Details |
|---|---|
| CPU | Intel Core Ultra 7 265K |
| Motherboard | ASUS ROG MAXIMUS Z890 APEX Hovedkort - Intel Z890 |
| RAM | Kingston FURY Beast DDR5-5600 - 64GB (32 Gb) |
| GPU | MSI GeForce RTX 5060 Ti (16 Gb GDDR7) |
| System | Linux 7.0.0-38-generic |
| llama.cpp version | llama.cpp@b11960 |
| Ollama version | ollama@v0.40.13 |
| vLLM version | vllm@0.27.1 |
| Model compression (llama.cpp) | gguf-Q4_K_M |
| Model compression (Ollama) | gguf-Q4_K_M |
| Model compression (vLLM) | awq-AWQ-4bit |

## Conclusion

For a single user on an RTX 5060 Ti, llama.cpp is the straightforward pick. It starts in about a second, matches Ollama on speed, and needs no server setup.

When several people share the same card, vLLM is the better fit. Its slower start-up matters little on a machine that stays running.

The practical limit is context length. Near the model's ceiling, the KV cache takes 12 GB of the card's 16 GB, and a full-length prompt takes **135 s** to process before the first word arrives. Short prompts are where this setup feels fast; feeding it whole documents is a different story.

## Further reading

**Every number, chart and caveat:** [the complete analysis](https://bench.auralis-lab.com/qwen3-5-4b-on-a-16-gb-rtx-5060-ti-260k-token-context-in-12-gb/).
