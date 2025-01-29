import streamlit as st
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from google.cloud import firestore
from prompts.company_info_prompt import company_info_prompt
from utils.flatten_dict import flatten_dict
from db.db import get_jobs
from models.suitability_rating import SuitabilityRating
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
from utils.get_model import get_model, available_models


def create_streamlit_app():
    st.set_page_config(layout="wide")

    # Initialize session state variables
    if 'job_offset' not in st.session_state:
        st.session_state.job_offset = 0
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
            new_jobs = get_jobs(offset=st.session_state.job_offset)
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
                        with st.spinner("Analyzing job suitability..."):
                            # Get the selected model and create suitability agent
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

