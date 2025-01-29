from google.cloud import firestore
from google.oauth2 import service_account
from google.oauth2 import service_account
from utils.flatten_dict import flatten_dict
import streamlit as st

project_id = st.secrets.get("project_id")
private_key_id = st.secrets.get("private_key_id")
private_key = st.secrets.get("private_key")
client_email = st.secrets.get("client_email")
client_id = st.secrets.get("client_id")
auth_uri = st.secrets.get("auth_uri")
token_uri = st.secrets.get("token_uri")
auth_provider_x509_cert_url = st.secrets.get("auth_provider_x509_cert_url")
client_x509_cert_url = st.secrets.get("client_x509_cert_url")
universe_domain = st.secrets.get("universe_domain")

credentials_dict = {
    "type": "service_account",
    "project_id": project_id,
    "private_key_id": private_key_id,
    "private_key": private_key,
    "client_email": client_email,
    "client_id": client_id,
    "auth_uri": auth_uri,
    "token_uri": token_uri,
    "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
    "client_x509_cert_url": client_x509_cert_url,
    "universe_domain": universe_domain,
}

db = firestore.Client().from_service_account_info(credentials_dict)



def get_jobs(limit=10, offset=0):
    """Fetch jobs from Firestore with pagination"""
    jobs_ref = db.collection('jobs').where('category', '==', 'Web Development').limit(limit).offset(offset)
    jobs = jobs_ref.get()
    jobs = [flatten_dict(job.to_dict()) for job in jobs]
    
    fields = ['description', 'title']
    
    return [{field: job.get(field, '') for field in fields} for job in jobs]