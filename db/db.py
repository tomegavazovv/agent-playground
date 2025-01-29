from google.cloud import firestore
from utils.flatten_dict import flatten_dict
import streamlit as st
from dotenv import load_dotenv
import os
import json

load_dotenv()

credentials_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
db = firestore.Client().from_service_account_info(credentials_dict)

def get_jobs(limit=10, offset=0):
    """Fetch jobs from Firestore with pagination"""
    jobs_ref = db.collection('jobs').where('category', '==', 'Web Development').limit(limit).offset(offset)
    jobs = jobs_ref.get()
    jobs = [flatten_dict(job.to_dict()) for job in jobs]
    
    fields = ['description', 'title']
    
    return [{field: job.get(field, '') for field in fields} for job in jobs]