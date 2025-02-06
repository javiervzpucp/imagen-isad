import os
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import json
from openai import OpenAI
from datetime import datetime
import requests
from PIL import Image
import tempfile

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
openai_api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=openai_api_key)

# Cargar metadatos desde JSON
metadata_path = 'metadata.json'
with open(metadata_path, 'r', encoding='ISO-8859-1') as f:
    metadata = json.load(f)

# Inicializar DataFrame vacío
if os.path.exists('descripciones_imagenes.csv'):
    new_df = pd.read_csv('descripciones_imagenes.csv', sep=';', encoding='ISO-8859-1')
else:
    new_df = pd.DataFrame(columns=["imagen", "descripcion", "generated_description", "keywords", "fecha"])

# Prompts para descripciones y palabras clave
describe_system_prompt = """
Eres un sistema archivístico especializado en la catalogación de fotografías históricas. 
Tu objetivo es generar descripciones precisas y detalladas de imágenes pertenecientes a la Colección Elejalde del Instituto Riva-Agüero de la PUCP.
Utiliza un enfoque archivístico basado en los principios de documentación histórica y cultural, asegurando que las descripciones reflejen el contexto histórico, arquitectónico y social de la imagen.
Evita interpretaciones modernas o elementos que no sean visibles en la imagen.
""" 

keyword_system_prompt = """
Eres un archivista digital especializado en la indexación de imágenes históricas de Lima y el Perú.
Genera palabras clave precisas y relevantes para facilitar la búsqueda y catalogación en bases de datos patrimoniales.
Debes incluir términos relacionados con la arquitectura, eventos históricos, personajes y lugares documentados en la imagen.
La respuesta debe ser un arreglo JSON con las palabras clave.
Ejemplo: ["arquitectura republicana", "Lima", "siglo XIX", "Patrimonio cultural", "Historia urbana"].
""" 

# Funciones
def validate_image_url(url):
    try:
        response = requests.head(url)
        return response.status_code == 200 and "image" in response.headers["content-type"]
    except Exception:
        return False

def describe_image(img_path, title):
    metadata_entry = next((item for item in metadata.get('files', []) if item.get('label') == title), None)
    additional_info = metadata_entry['description'] if metadata_entry else ''
    
    excel_entry = new_df[new_df['imagen'] == title]
    excel_info = excel_entry['descripcion'].values[0] if not excel_entry.empty else ''
    
    prompt = f"{describe_system_prompt}\n\nContexto archivístico:\n{additional_info}\nInformación adicional de Excel:\n{excel_info}\n\nGenera una descripción detallada y precisa para la siguiente imagen:\nTítulo: {title}"
    
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": describe_system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

def generate_keywords(description):
    prompt = f"{keyword_system_prompt}\n\nDescripción de la imagen:\n{description.strip()}"
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": keyword_system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        temperature=0.2
    )
    try:
        keywords = json.loads(response.choices[0].message.content.strip())
        if isinstance(keywords, list):
            return keywords
        else:
            return ["Sin datos"]
    except json.JSONDecodeError:
        return []

def save_to_csv(dataframe, file_path):
    dataframe.to_csv(file_path, sep=';', index=False, encoding='ISO-8859-1')

# Interfaz de Streamlit
st.title("Generador de Descripciones de Imágenes Históricas")
option = st.radio("Seleccione el método para proporcionar una imagen:", ("URL de imagen", "Subir imagen"))

if option == "URL de imagen":
    img_url = st.text_input("Ingrese la URL de la imagen")
    title = st.text_input("Ingrese un título o descripción breve de la imagen")
    
    if img_url and validate_image_url(img_url):
        st.image(img_url, caption="Imagen desde URL", use_column_width=True)
        if st.button("Generar Descripción"):
            description = describe_image(img_url, title)
            keywords = generate_keywords(description)
            st.write("Descripción generada:", description)
            st.write("Palabras clave generadas:", ", ".join(keywords))
            new_row = {"imagen": img_url, "descripcion": title, "generated_description": description, "keywords": keywords, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            new_df = pd.concat([new_df, pd.DataFrame([new_row])], ignore_index=True)
            
            save_to_csv(new_df, 'descripciones_imagenes.csv')
else:
    uploaded_file = st.file_uploader("Cargue una imagen", type=["jpg", "jpeg", "png"])
    title = st.text_input("Ingrese un título o descripción breve de la imagen")
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Imagen cargada", use_column_width=True)
        if st.button("Generar Descripción"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                image.save(temp_file.name)
                img_path = temp_file.name
            description = describe_image(img_path, title)
            keywords = generate_keywords(description)
            st.write("Descripción generada:", description)
            st.write("Palabras clave generadas:", ", ".join(keywords))
            new_row = {"imagen": img_path, "descripcion": title, "generated_description": description, "keywords": keywords, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            new_df = pd.concat([new_df, pd.DataFrame([new_row])], ignore_index=True)
            
            save_to_csv(new_df, 'descripciones_imagenes.csv')
                
