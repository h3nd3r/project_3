from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_showtimes, get_now_playing_movies, get_reviews
import re
import json


load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
from langsmith.wrappers import wrap_openai
from langsmith import traceable
import openai
client = wrap_openai(openai.AsyncClient())

# from langfuse.decorators import observe
# from langfuse.openai import AsyncOpenAI
 
# client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}

# SYSTEM_PROMPT = """\
# You are a helpful assistant.

# If you have the information in the context use it to reply.

# otherwise if asked about showtimes reply with the movie title and location formatted as follows:
# { "function": "get_showtimes", "title": "movieTitle", "location": "city, state"}

# if asked about current movies playing, you will create a message formatted as 
# { "function": "get_now_playing_movies"}

# and if asked about the reviews for a movie, you will create a message formatted as
# { "function": "get_reviews", "movie_id": "movieId" }


# """

SYSTEM_PROMPT = """\
You are a helpful movie chatbot that helps people explore movies that are out in \
theaters. If a user asks for recent information, output a function call and \
the system add to the context. If you need to call a function, only output the \
function call. Call functions using Python syntax in plain text, no code blocks.

You have access to the following functions, generate function calls in the following format:
{ "function": "get_showtimes", "title": "movieTitle", "location": "city, state"}

{ "function": "get_now_playing_movies"}

{ "function": "get_reviews", "movie_id": "movieId" }
"""


# @observe
@traceable
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

# @observe
@traceable
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@cl.on_message
#@observe
@traceable
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})

    response_message = await generate_response(client, message_history, gen_kwargs)

    if response_message.content.startswith("{ \"function\": "):
        print("Function call detected")
        

        try:
            json_message = json.loads(response_message.content)
        
            function_name = json_message.get("function")
            
            if function_name == "get_showtimes":
                title = json_message.get("title")
                location = json_message.get("location")
                result = get_showtimes(title, location)
            elif function_name == "get_now_playing_movies":
                result = get_now_playing_movies()
            elif function_name == "get_reviews":
                movie_id = json_message.get("movie_id")
                result = get_reviews(movie_id)
            else:
                result = "Unknown function call"
                
            message_history.append({"role": "system", "content": result})
            
            # print("result:", result)
            response_message = await generate_response(client, message_history, gen_kwargs)
            

            # title = json_message.get("title")
            # location = json_message.get("location") 
            # showtimes = get_showtimes(title, location)
            # message_history.append({"role": "assistant", "content": showtimes})
            # response_message = await generate_response(client, message_history, gen_kwargs)
        except json.JSONDecodeError:
            print("Error: Unable to parse the message as JSON")
            json_message = None
    
    message_history.append({"role": "assistant", "content": response_message.content})


    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()
