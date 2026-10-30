---
title: "qwen3.5-4b - Budget computer"
description: "qwen3.5-4b - Budget computer"
tags: [ai, llm, benchmark, devops]
cover: "images/cover.png"
issue: "565bc5bf-e3b5-4088-8a82-34af462e8838"
---

Qwen3.5-4B writes **114 tokens per second** on a short prompt and uses **0.63 kWh per 1M generated tokens**. Hand it a 100-page book and it starts answering after 6.5 s, then writes 21 times faster than you can read. It is a small 4-billion-parameter language model, a size suited to mobile or edge devices rather than the broader analysis and general-knowledge work expected from larger models. Every program was tested exactly as it installs, with no tuning, on an NVIDIA GeForce RTX 5060 Ti.

## Straight to the Results

Qwen3.5-4b on an NVIDIA GeForce RTX 5060 Ti is a niche edge-inference option, classified as suitable for short prompts but slow at full context.

- Speed: **114 tokens per second** on a short prompt, down to **34 tokens per second** at full context.
- Waiting: the first word arrives in **101 ms** on a short prompt, but takes **6.5 s** on a 32k-token prompt.
- Electricity: **0.63 kWh per 1M generated tokens**, costing about 0.16 €.

The results were measured with llama.cpp, as it installs:


| Metric                    | 512 Context | 32k Context | Max Context (262144) |
| ------------------------- | ----------- | ----------- | -------------------- |
| Prompt Processing (tok/s) | 5050.03     | 5031.2      | 1945.92              |
| TTFT                      | 101 ms      | 6.5 s       | 135 s                |
| Generation (tok/s)        | 113         | 88          | 33                   |

## Which Program Should You Run It With?

The same model was run with llama.cpp, Ollama and vLLM, three free programs for running models at home. Each was used exactly as it installs.


|                                     | llama.cpp  | Ollama     | vLLM     |
| ----------------------------------- | ---------- | ---------- | -------- |
| Writing speed, short prompt (tok/s) | 113.757    | 113.619    | 107.4    |
| Wait for first word, short prompt   | 101.386 ms | 164.781 ms | 101 ms   |
| Wait for first word, 32k prompt     | 6.5 s      | 7.3 s      | 7.5 s    |
| Longest context (tokens)            | 262k       | 262k       | 256k     |
| Start-up time                       | 1.027 s    | 4.745 s    | 47.641 s |
| Electricity (kWh per 1M tokens)     | 0.62608    | 0.65178    | 0.52414  |


llama.cpp wins writing speed, both waits for the first word and start-up, and ties Ollama for longest context; vLLM wins on electricity at **0.52 kWh per 1M tokens**. For one person on their own machine, llama.cpp is the fastest pick, Ollama is the easiest-install option with nearly the same short-prompt writing speed, and vLLM is the choice for serving several people, though its start-up takes **48 s**. The model files differ: vLLM uses the awq-AWQ-4bit compressed version, while the other two use gguf-Q4\_K\_M.

## Writing Speed as the Conversation Grows

![Writing speed vs context size](images/writing-speed-vs-context-size.png)

Writing speed holds up fairly well to 32k context, then drops sharply: llama.cpp goes from **114 tokens per second** at 512 tokens to 88 at 32k and **34 tokens per second** at full context. Ollama tracks it almost exactly, while vLLM is slightly slower at the smaller contexts but slightly faster at its own maximum, reaching 36 tokens per second. vLLM’s bar is missing at the largest sizes because it cannot hold that much context. At full context, llama.cpp’s first word appears only after 135 s.

## When Many People Use It at Once

![Total tokens produced per second vs simultaneous users](images/total-tokens-produced-per-second-vs-simultaneous-users.png)

So far, every number was measured for one person using the model alone. With vLLM, a program built for sharing, the same computer serves 16 people at once: together they receive **823 tokens per second**, instead of 103 for one person alone. Each person still sees the first word after about 1.2 s. One budget computer can back a whole team or a small product, not just one user.

## The Test Bench

The hardware will remain unchanged throughout the entire series. This will make the results more comparable across different model series.

| Component | Specification |
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

All three programs did not run the same compressed version of the model, so the comparison between programs is not strictly like for like.

## Conclusion

On a budget computer with an NVIDIA GeForce RTX 5060 Ti, qwen3.5-4b is usable, with decoding from 34 to **114 tokens per sectheond** and energy use of 0.63 kWh per 1M generated tokens. The fastest response time is 101 ms; the slowest is 135 s at 260k tokens. On a short prompt, llama.cpp and Ollama both reach 114 tokens per second, ahead of vLLM at 107, while vLLM serves 16 users at **823 tokens per second** in total. For one person, I would pick llama.cpp; for several people, vLLM.
