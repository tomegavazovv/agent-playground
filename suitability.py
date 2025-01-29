import streamlit as st
import logging
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from google.cloud import firestore

from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
from utils.get_model import get_model, available_models

from google.cloud import firestore
from utils.flatten_dict import flatten_dict
import streamlit as st
from langchain_openai import  ChatOpenAI
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager
from langchain_anthropic import ChatAnthropic
from langchain_openai.chat_models.base import BaseChatOpenAI
import os

company_info_prompt = """
# Role

You are an AI Agent tasked with assessing how suitable a given Upwork job post is for MVP Masters, returning a score from 0 to 100.

---

# Instructions

1. **Input**: You will receive the job's title and description.
2. **Action**: Compare the job requirements against the "Knowledge Base" below.
3. **Output**: Provide:
   - A suitability rating (0 to 100) indicating how well this job aligns with MVP Masters' capabilities and preferences.
   - A succinct reasoning for that rating in **no more than two sentences**.

---

# Rules

1. If the job post explicitly requires skills or services **not** mentioned in the knowledge base, score it close to 0.
2. If the job fits well with MVP Masters' described areas of expertise, approaches, technologies, and project types, score it closer to 100.
3. Be **strict**: if something is not clearly within MVP Masters' capabilities (as stated in the knowledge base), assume they **do not provide** it.
4. Do not provide additional commentary beyond the rating and reasoning.

---

# Knowledge Base

## Summary

MVP Masters is a tech partner dedicated to assisting entrepreneurs in successfully developing their products. They specialize in end-to-end product development, streamlining product management, workflows, processes, integrations, and data analytics to ensure products stay on track and deliver results.

## Specialty

MVP Masters excels in:

- **Lean Engineering**: Building fast and smart using robust yet scalable technologies, ready-made components, and top-notch integration tools, coding with the speed of no-code.
- **User-Centric Design**: Designing with customers in mind, creating functional, intuitive, and impactful designs through discovery and user feedback.
- **Product Management**: Simplifying product management from project execution to strategy, analytics, and discovery.

## Types of Projects We Take On

### Engagement-Based

- **End-to-End Product Development**: Full-cycle product development from discovery to post-launch growth.
- **Green-Field Projects**: Projects that require building a product from scratch.
- **Long-Term Engagements**: Multi-month or multi-year engagements where MVP Masters plays a strategic role in building and scaling the product.

### Industry-Based

- **B2B SaaS Applications**: Automation, analytics, integrations.
- **PropTech Solutions**: Real estate and property management.
- **E-Commerce & Marketplaces**: Including CRM/ERP integrations.
- **Social & Community Platforms**: User engagement, social interaction, gamification.
- **FinTech Solutions**: Secure, scalable financial applications with compliance.
- **AI & Automation**: Products leveraging AI, ML, and automation tools.

### Project Complexity

MVP Masters typically handles full-scope or substantial product builds rather than small tasks or fixes.

## Types of Projects We Avoid

- **Technology-Specific Constraints** outside of their tech stack.
- **Team Augmentation** where only a developer is needed to join an existing team.
- **Maintenance-Only Work** on legacy or existing software.
- **Small Gigs & Fixes** (bug fixes, minor adjustments).
- **Answering Technical Questions** (consulting-only without execution).

## Examples of Projects They Take On

- **Dubbing CRM Web Applications** (Voice dubbing, CRMs, automation).
- **Sports Social Network Mobile Applications** (User rating, social features).
- **Hospitality PropTech Web & Mobile Applications** (Property optimization).
- **Home Improvement E-Commerce Platforms** (Full-scale e-commerce with significant integrations).
- **ERP/CRM Systems for Niche Markets** (Custom ERP/CRM solutions).
- **Spiritual Web Applications** (Focused on user-centric experiences).

## Approach

1. **Discovery & Shaping**
2. **Prototyping & Ideation**
3. **Design & Development**
4. **Alpha/Beta Stages**
5. **Live MVP**
6. **Growing Product**

## Technologies They Use

- **Front-end**: Next.js, MUI, React Native
- **Back-end**: Nest.js, Node.js, Firebase
- **Infrastructure**: Google Cloud Platform (GCP), Amazon Web Services (AWS), Terraform
- **Data**: Posthog, Mixpanel, Google Analytics 4 (GA4)

## Location

- Venice, CA, USA
- Tallinn, Estonia
- Skopje, Macedonia

## Selected Case Studies

- **Human Voice Over (HVO)**: Dubbing CRM Web Application.
- **RateGame**: Sports social network mobile app.
- **Hububb**: Hospitality PropTech platform (web + mobile).
- **Cabinet Deals**: Home improvement e-commerce platform.
- **KBB Suite**: CRM/ERP for kitchen cabinet showrooms.

---

Please use the above knowledge base to strictly evaluate the provided job post.

"""

def flatten_dict(d):
    items = []
    for k, v in d.items():
        new_key = f"{k}" 
        if isinstance(v, dict):
            items.extend(flatten_dict(v).items())
        else:
            items.append((new_key, v))
    return dict(items)

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



credentials_dict = st.secrets['gcp_service_account']
db = firestore.Client().from_service_account_info(credentials_dict)

def get_jobs(limit=10, offset=0):
    """Fetch jobs from Firestore with pagination"""
    jobs_ref = db.collection('jobs').where('category', '==', 'Web Development').limit(limit).offset(offset)
    jobs = jobs_ref.get()
    jobs = [flatten_dict(job.to_dict()) for job in jobs]
    
    fields = ['description', 'title']
    
    return [{field: job.get(field, '') for field in fields} for job in jobs]

from pydantic import BaseModel, Field

class SuitabilityRating(BaseModel):
    suitability_score: str = Field(description="A score between 0 and 100 indicating the suitability of the job post for the company")
    reason: str = Field(description="A detailed explanation of the suitability score. Max 2 sentences.")
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_streamlit_app():
    logger.info("Starting Streamlit app")
    st.set_page_config(layout="wide")

    # Initialize session state variables
    if 'job_offset' not in st.session_state:
        st.session_state.job_offset = 0
        logger.info("Initialized job_offset")
    if 'loaded_jobs' not in st.session_state:
        st.session_state.loaded_jobs = []
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'gpt-4o'
    
    st.markdown("""
        <style>
        .st-key-jobs-container {
            height: 70vh;
            max-height: 70vh;
            min-height: 70vh;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #ddd;
        }

        #text_area_1{
          background-color: white;
          padding: 10px;
          border: 1px solid #ddd;
          min-height: 50vh;
          max-height: 50vh;
        }

        .st-key-load_more_jobs_container{
          width: 100%;
          display: flex !important;
          justify-content: center;
          align-items: center;
        }
        </style>
    """, unsafe_allow_html=True)
    
    selected_model = st.selectbox(
            "Choose a model",
            options=available_models,
            index=available_models.index(st.session_state.selected_model)
        )
    col1, col2 = st.columns([1, 1])
    
    
    # Left column - Display the prompt and model selection
    with col1:
        
        
        # Update the selected model in session state if changed
        if selected_model != st.session_state.selected_model:
            st.session_state.selected_model = selected_model
        
        # Replace the disabled text area with an editable one and store in session state
        if 'company_prompt' not in st.session_state:
            st.session_state.company_prompt = company_info_prompt
        
        edited_prompt = st.text_area(
            "Edit Prompt", 
            value=st.session_state.company_prompt, 
            height=400
        )
        
        # Add update button
        if st.button("Update Prompt", type="primary"):
            st.session_state.company_prompt = edited_prompt
            st.success("Prompt updated successfully!")
    
    # Right column - Display jobs
    with col2:
        with st.container(key='jobs-container'):
            
            # Fetch new jobs and append to existing ones
            logger.info(f"Fetching jobs with offset {st.session_state.job_offset}")
            new_jobs = get_jobs(offset=st.session_state.job_offset)
            logger.info(f"Fetched {len(new_jobs)} new jobs")
            if not st.session_state.loaded_jobs or st.session_state.job_offset == 0:
                st.session_state.loaded_jobs = new_jobs
            
            # Display all loaded jobs
            for job in st.session_state.loaded_jobs:
                with st.container():
                    st.markdown(f"### {job['title']}")
                    
                    
                    
                    # Create a collapsible section for the full description
                    st.write(job['description'])
                    
                    # Add an analyze button
                    if st.button(f"Analyze Suitability", key=f"analyze_{job['title']}"):
                        logger.info(f"Analyzing suitability for job: {job['title']}")
                        with st.spinner("Analyzing job suitability..."):
                            # Get the selected model and create suitability agent
                            logger.info(f"Using model: {st.session_state.selected_model}")
                            model = get_model(st.session_state.selected_model)
                            suitability_agent = model.with_structured_output(SuitabilityRating)
                            
                            messages = [
                                {"role": "system", "content": st.session_state.company_prompt},
                                {"role": "user", "content": f"Job Title: {job['title']}\n\nJob Description: {job['description']}"}
                            ]
                            
                            result = suitability_agent.invoke(messages)
                            
                            # Display the results in a colored box
                            score = int(result.suitability_score)
                            color = "#ff6666" if score < 40 else "#ffaa66" if score < 70 else "#66bb66"
                            st.markdown(f"""
                                <div style='padding: 10px; background-color: {color}; border-radius: 5px;'>
                                    <h4 style='color: white;'>Suitability Score: {score}/100</h4>
                                    <p style='color: white;'>{result.reason}</p>
                                </div>
                            """, unsafe_allow_html=True)
                    st.markdown("---")
                      
            
            with st.container(key='load_more_jobs_container'):
              if st.button("Load More Jobs", type="primary", use_container_width=True):
                  st.session_state.job_offset += 10
                  new_jobs = get_jobs(offset=st.session_state.job_offset)
                  st.session_state.loaded_jobs.extend(new_jobs)
                  st.rerun()

if __name__ == "__main__":
    create_streamlit_app()

