"""
Dummy summarisation placeholder for future local LLM on GPU 1.

FUTURE IMPLEMENTATION:
This module will be modified to load and run a real local LLM (e.g., LLaMA, Qwen)
on GPU 1 using settings.LLM_DEVICE = "cuda:1".

Example future implementation with HuggingFace transformers:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    tokenizer = AutoTokenizer.from_pretrained("model-name")
    model = AutoModelForCausalLM.from_pretrained("model-name").to(settings.LLM_DEVICE)
    
    def summarize_text(text: str, max_chars: int = 500) -> str:
        prompt = f"Summarize the following text:\\n\\n{text[:2000]}"
        inputs = tokenizer(prompt, return_tensors="pt").to(settings.LLM_DEVICE)
        outputs = model.generate(**inputs, max_new_tokens=200)
        summary = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return summary
"""
import logging
from .config import settings


logger = logging.getLogger(__name__)


def summarize_text(text: str, max_chars: int = 500) -> str:
    """
    Dummy summariser placeholder for a future local LLM (e.g. LLaMA/Qwen) on GPU 1.
    
    Current behaviour:
    - If text is longer than max_chars, truncate it.
    - Return a simple string indicating this is a dummy implementation.
    
    Future behaviour:
    - This function will load and run a real local LLM on settings.LLM_DEVICE (cuda:1).
    - The LLM will generate an actual intelligent summary of the transcript.
    
    Args:
        text: The full transcript text to summarize.
        max_chars: Maximum characters to include in the dummy summary.
        
    Returns:
        Summary string (currently dummy implementation).
    """
    logger.info(f"Generating summary (dummy mode) for text of length {len(text)}")
    
    # Truncate if text is too long
    trimmed_text = text[:max_chars]
    if len(text) > max_chars:
        trimmed_text += "..."
    
    # Return dummy summary with clear indication of future LLM device
    summary = f"Summary (dummy, future LLM on {settings.LLM_DEVICE}): {trimmed_text}"
    
    logger.info(f"Summary generated (dummy mode). Length: {len(summary)}")
    
    return summary
