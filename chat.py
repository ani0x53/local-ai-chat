"""
Local ChatGPT-like chatbot using TinyLlama Chat.

Install deps:
    pip install transformers torch accelerate
"""

from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


def load_model():
    print(f"Loading {MODEL_NAME} (first time downloads ~2GB)...")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    pipe = pipeline(
        "text-generation",
        model=MODEL_NAME,
        torch_dtype=torch.float32,
        device=device,
    )
    return pipe


def main():
    pipe = load_model()
    print("\nChat is ready! Type 'quit' to exit.\n")

    messages = [
        {"role": "system", "content": "You are a helpful, friendly assistant. Give clear and concise answers."},
    ]

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        outputs = pipe(
            messages,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )

        response = outputs[0]["generated_text"][-1]["content"]

        messages.append({"role": "assistant", "content": response})

        print(f"Assistant: {response}\n")


if __name__ == "__main__":
    main()
