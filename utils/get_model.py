from langchain_openai import  ChatOpenAI
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager
from langchain_anthropic import ChatAnthropic
from langchain_openai.chat_models.base import BaseChatOpenAI
import os

available_models = ['deepseek-chat', 'gpt-4', 'gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet-20240620']

tracer = LangChainTracer(
    project_name="chatbot-upleads"
)

def get_model(name: str):
  if name not in available_models:
    raise ValueError(f"Model {name} not found. Available models: {available_models}")
  
  if 'gpt' in name:
    return ChatOpenAI(
      model=name,
      temperature=0,
      callback_manager=CallbackManager([tracer])
    )
  elif 'deepseek' in name:
    return BaseChatOpenAI(
      model=name,
      openai_api_key=os.getenv('DEEPSEEK_API_KEY'),
      openai_api_base="https://api.deepseek.com",
      max_tokens=1024,
      temperature=0,
      callback_manager=CallbackManager([tracer])
    )
  elif 'claude' in name:
    return ChatAnthropic(
      model=name,
      temperature=0,
      max_tokens=1024,
      timeout=None,
      max_retries=2,
      api_key=os.getenv('ANTHROPIC_API_KEY'),
      callback_manager=CallbackManager([tracer])
    )
  # if name == 'deepseek':
  #   return BaseChatOpenAI(
  #           model="deepseek-chat",
  #           openai_api_key="sk-8e128b8744524265be579501612ee5c1",
  #           openai_api_base="https://api.deepseek.com",
  #           max_tokens=1024,
  #           temperature=0
  #       )
  # elif name == 'gpt-4':
  #   return ChatOpenAI(
  #           model="gpt-4",
  #           temperature=0
  #       )

