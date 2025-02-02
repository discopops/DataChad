import streamlit as st
from streamlit_chat import message

from constants import (
    ACTIVELOOP_HELP,
    APP_NAME,
    AUTHENTICATION_HELP,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_DATA_SOURCE,
    EMBEDDINGS,
    ENABLE_ADVANCED_OPTIONS,
    FETCH_K,
    MAX_TOKENS,
    MODEL,
    OPENAI_HELP,
    PAGE_ICON,
    PROJECT_URL,
    TEMPERATURE,
    USAGE_HELP,
    K,
)
from utils import (
    authenticate,
    delete_uploaded_file,
    generate_response,
    logger,
    save_uploaded_file,
    update_chain,
)

# Page options and header
st.set_option("client.showErrorDetails", True)
st.set_page_config(
    page_title=APP_NAME, page_icon=PAGE_ICON, initial_sidebar_state="expanded"
)
st.markdown(
    f"<h1 style='text-align: center;'>{APP_NAME} {PAGE_ICON} <br> I know all about your data!</h1>",
    unsafe_allow_html=True,
)


SESSION_DEFAULTS = {
    "past": [],
    "usage": {},
    "chat_history": [],
    "generated": [],
    "data_source": DEFAULT_DATA_SOURCE,
    "uploaded_file": None,
    "auth_ok": False,
    "openai_api_key": None,
    "activeloop_token": None,
    "activeloop_org_name": None,
    "model": MODEL,
    "embeddings": EMBEDDINGS,
    "k": K,
    "fetch_k": FETCH_K,
    "chunk_size": CHUNK_SIZE,
    "chunk_overlap": CHUNK_OVERLAP,
    "temperature": TEMPERATURE,
    "max_tokens": MAX_TOKENS,
}
# Initialise session state variables
for k, v in SESSION_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def authentication_form() -> None:
    st.title("Authentication", help=AUTHENTICATION_HELP)
    with st.form("authentication"):
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help=OPENAI_HELP,
            placeholder="This field is mandatory",
        )
        activeloop_token = st.text_input(
            "ActiveLoop Token",
            type="password",
            help=ACTIVELOOP_HELP,
            placeholder="Optional, using ours if empty",
        )
        activeloop_org_name = st.text_input(
            "ActiveLoop Organisation Name",
            type="password",
            help=ACTIVELOOP_HELP,
            placeholder="Optional, using ours if empty",
        )
        submitted = st.form_submit_button("Submit")
        if submitted:
            authenticate(openai_api_key, activeloop_token, activeloop_org_name)


def advanced_options_form() -> None:
    # Input Form that takes advanced options and rebuilds chain with them
    advanced_options = st.checkbox(
        "Advanced Options", help="Caution! This may break things!"
    )
    if advanced_options:
        with st.form("advanced_options"):
            temperature = st.slider(
                "temperature",
                min_value=0.0,
                max_value=1.0,
                value=TEMPERATURE,
                help="Controls the randomness of the language model output",
            )
            col1, col2 = st.columns(2)
            fetch_k = col1.number_input(
                "k_fetch",
                min_value=1,
                max_value=1000,
                value=FETCH_K,
                help="The number of documents to pull from the vector database",
            )
            k = col2.number_input(
                "k",
                min_value=1,
                max_value=100,
                value=K,
                help="The number of most similar documents to build the context from",
            )
            chunk_size = col1.number_input(
                "chunk_size",
                min_value=1,
                max_value=100000,
                value=CHUNK_SIZE,
                help=(
                    "The size at which the text is divided into smaller chunks "
                    "before being embedded.\n\nChanging this parameter makes re-embedding "
                    "and re-uploading the data to the database necessary "
                ),
            )
            max_tokens = col2.number_input(
                "max_tokens",
                min_value=1,
                max_value=4069,
                value=MAX_TOKENS,
                help="Limits the documents returned from database based on number of tokens",
            )
            applied = st.form_submit_button("Apply")
            if applied:
                st.session_state["k"] = k
                st.session_state["fetch_k"] = fetch_k
                st.session_state["chunk_size"] = chunk_size
                st.session_state["temperature"] = temperature
                st.session_state["max_tokens"] = max_tokens
                update_chain()


# Sidebar with Authentication and Advanced Options
with st.sidebar:
    authentication_form()

    st.info(f"Learn how it works [here]({PROJECT_URL})")
    # Only start App if authentication is OK
    if not st.session_state["auth_ok"]:
        st.stop()

    # Clear button to reset all chat communication
    clear_button = st.button("Clear Conversation", key="clear")

    # Advanced Options
    if ENABLE_ADVANCED_OPTIONS:
        advanced_options_form()

if clear_button:
    # resets all chat history related caches
    st.session_state["past"] = []
    st.session_state["generated"] = []
    st.session_state["chat_history"] = []


# file upload and data source inputs
uploaded_file = st.file_uploader("Upload a file")
data_source = st.text_input(
    "Enter any data source",
    placeholder="Any path or url pointing to a file or directory of files",
)

# the chain can only be initialized after authentication is OK
if "chain" not in st.session_state:
    update_chain()

# generate new chain for new data source / uploaded file
# make sure to do this only once per input / on change
if data_source and data_source != st.session_state["data_source"]:
    logger.info(f"Data source provided: '{data_source}'")
    st.session_state["data_source"] = data_source
    update_chain()

if uploaded_file and uploaded_file != st.session_state["uploaded_file"]:
    logger.info(f"Uploaded file: '{uploaded_file.name}'")
    st.session_state["uploaded_file"] = uploaded_file
    data_source = save_uploaded_file()
    st.session_state["data_source"] = data_source
    update_chain()
    delete_uploaded_file()


# container for chat history
response_container = st.container()
# container for text box
text_container = st.container()

# As streamlit reruns the whole script on each change
# it is necessary to repopulate the chat containers
with text_container:
    with st.form(key="prompt_input", clear_on_submit=True):
        user_input = st.text_area("You:", key="input", height=100)
        submit_button = st.form_submit_button(label="Send")

if submit_button and user_input:
    output = generate_response(user_input)
    st.session_state["past"].append(user_input)
    st.session_state["generated"].append(output)

if st.session_state["generated"]:
    with response_container:
        for i in range(len(st.session_state["generated"])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + "_user")
            message(st.session_state["generated"][i], key=str(i))


# Usage sidebar with total used tokens and costs
# We put this at the end to be able to show usage starting with the first response
with st.sidebar:
    if st.session_state["usage"]:
        st.divider()
        st.title("Usage", help=USAGE_HELP)
        col1, col2 = st.columns(2)
        col1.metric("Total Tokens", st.session_state["usage"]["total_tokens"])
        col2.metric("Total Costs in $", st.session_state["usage"]["total_cost"])
