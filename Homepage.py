import streamlit as st
import os
import tempfile
import io
import random


from langchain.document_loaders import PyPDFLoader
from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import ast

# from helpers.quiz_utils import get_quiz_data


st.set_page_config(
    page_title="Clearly",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed")


def string_to_list(s):
    try:
        return ast.literal_eval(s)
    except (SyntaxError, ValueError) as e:
        st.error(f"Error: The provided input is not correctly formatted. {e}")
        st.stop()

def get_randomized_options(options):
    correct_answer = options[0]
    random.shuffle(options)
    return options, correct_answer

def extract_text_from_pdf(file_obj):
    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "temp_pdf.pdf")

    # Write the content of the file object to the temporary file
    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(file_obj.read())

    # Initialize the PyPDFLoader with the temporary file path
    pdf_loader = PyPDFLoader(temp_file_path)
    document_list = pdf_loader.load_and_split()  # This returns a list of Document objects

    # Extract text from each Document object
    combined_text = " ".join([doc.page_content for doc in document_list])

    # Optionally, delete the temporary file and directory here if you want to clean up
    os.remove(temp_file_path)
    os.rmdir(temp_dir)

    return combined_text

def get_quiz_data(text, openai_api_key):
    template = f"""
    You are a helpful assistant programmed to generate questions based on any text provided. For every chunk of text you receive, you're tasked with designing 5 distinct questions. Each of these questions will be accompanied by 3 possible answers: one correct answer and two incorrect ones. 

    For clarity and ease of processing, structure your response in a way that emulates a Python list of lists. 

    Your output should be shaped as follows:

    1. An outer list that contains 5 inner lists.
    2. Each inner list represents a set of question and answers, and contains exactly 4 strings in this order:
    - The generated question.
    - The correct answer.
    - The first incorrect answer.
    - The second incorrect answer.

    Your output should mirror this structure:
    [
        ["Generated Question 1", "Correct Answer 1", "Incorrect Answer 1.1", "Incorrect Answer 1.2"],
        ["Generated Question 2", "Correct Answer 2", "Incorrect Answer 2.1", "Incorrect Answer 2.2"],
        ...
    ]

    It is crucial that you adhere to this format as it's optimized for further Python processing.

    """
    try:
        system_message_prompt = SystemMessagePromptTemplate.from_template(template)
        human_message_prompt = HumanMessagePromptTemplate.from_template("{text}")
        chat_prompt = ChatPromptTemplate.from_messages(
            [system_message_prompt, human_message_prompt]
        )
        chain = LLMChain(
            llm=ChatOpenAI(model_name="gpt-3.5-turbo-1106", openai_api_key=OPENAI_API_KEY),
            prompt=chat_prompt,
        )
        quiz_data = chain.run(extracted_text)
    
        quiz_data_clean = ast.literal_eval(quiz_data)
        return chain.run(text)
    
    except Exception as e:
        if "AuthenticationError" in str(e):
            st.error("Incorrect API key provided. Please check and update your API key.")
            st.stop()
        else:
            st.error(f"An error occurred: {str(e)}")
            st.stop()

            
st.subheader("MCQ for your PDF")


# Create form for user input
with st.form("user_input"):
    OPENAI_API_KEY = st.text_input("Enter your OpenAI API Key:", placeholder="sk-XXXX", type='password')
    uploaded_files = st.file_uploader("Choose a PDF file")
    submitted = st.form_submit_button("Craft my quiz!")

if submitted or ('quiz_data_list' in st.session_state):
    if not uploaded_files:
        st.info("Please provide a valid PDF document")
        st.stop()
    elif not OPENAI_API_KEY:
        st.info("Please fill out the OpenAI API Key to proceed. If you don't have one, you can obtain it [here](https://platform.openai.com/account/api-keys).")
        st.stop()
        
    with st.spinner("Crafting your quiz...🤓"):
        if submitted:
            extracted_text = extract_text_from_pdf(uploaded_files)
            quiz_data_str = get_quiz_data(extracted_text, OPENAI_API_KEY)
            st.session_state.quiz_data_list = string_to_list(quiz_data_str)
        if 'user_answers' not in st.session_state:
            st.session_state.user_answers = [None for _ in st.session_state.quiz_data_list]
        if 'correct_answers' not in st.session_state:
            st.session_state.correct_answers = []
        if 'randomized_options' not in st.session_state:
            st.session_state.randomized_options = []
        for q in st.session_state.quiz_data_list:
            options, correct_answer = get_randomized_options(q[1:])
            st.session_state.randomized_options.append(options)
            st.session_state.correct_answers.append(correct_answer)

        with st.form(key='quiz_form'):
            st.subheader("🧠 Test Your Knowledge!", anchor=False)
            for i, q in enumerate(st.session_state.quiz_data_list):
                options = st.session_state.randomized_options[i]
                default_index = st.session_state.user_answers[i] if st.session_state.user_answers[i] is not None else 0
                response = st.radio(q[0], options, index=default_index)
                user_choice_index = options.index(response)
                st.session_state.user_answers[i] = user_choice_index  # Update the stored answer right after fetching it

            results_submitted = st.form_submit_button(label='Submit')

            if results_submitted:
                score = sum([ua == st.session_state.randomized_options[i].index(ca) for i, (ua, ca) in enumerate(zip(st.session_state.user_answers, st.session_state.correct_answers))])
                st.success(f"Your score: {score}/{len(st.session_state.quiz_data_list)}")

                if score == len(st.session_state.quiz_data_list):  # Check if all answers are correct
                    st.balloons()
                else:
                    incorrect_count = len(st.session_state.quiz_data_list) - score
                    if incorrect_count == 1:
                        st.warning(f"Almost perfect! You got 1 question wrong. Let's review it:")
                    else:
                        st.warning(f"Almost there! You got {incorrect_count} questions wrong. Let's review them:")

                for i, (ua, ca, q, ro) in enumerate(zip(st.session_state.user_answers, st.session_state.correct_answers, st.session_state.quiz_data_list, st.session_state.randomized_options)):
                    with st.expander(f"Question {i + 1}", expanded=False):
                        if ro[ua] != ca:
                            st.info(f"Question: {q[0]}")
                            st.error(f"Your answer: {ro[ua]}")
                            st.success(f"Correct answer: {ca}")
