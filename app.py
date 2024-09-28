from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_showtimes, get_now_playing_movies, get_reviews, buy_ticket
import re
import json
import openai
from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}

SYSTEM_PROMPT = """\
You are a helpful movie chatbot that helps people explore movies that are out in \
theaters. If a user asks for recent information, output a function call and \
the system add to the context. If you need to call a function, only output the \
function call. Call functions using Python syntax in plain text, no code blocks.

You have access to the following functions, generate function calls in the following format:
# get the available showtimes for a movie in a zipcode
{ "function": "get_showtimes", "title": "movieTitle", "location": "zipcode"}

# get the list of movies currently playing
{ "function": "get_now_playing_movies"}

# get the reviews for a movie
{ "function": "get_reviews", "movie_id": "movieId" }

# initiate a ticket purchase, confirm the ticket purchase with the user before finalizing by calling the confirm_ticket_purchase function
{ "function": "buy_ticket", "theater": "theaterName", "movie": "movieTitle", "showtime": "showtime" }

# confirm a ticket purchase
{ "function": "confirm_ticket_purchase", "theater": "theaterName", "movie": "movieTitle", "showtime": "showtime" }

"""

@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
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
@observe
async def on_message(message: cl.Message):

    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})

    response_message = await generate_response(client, message_history, gen_kwargs)

    while response_message.content.startswith("{ \"function\": "):

        print("Function call detected with response_message: \"", response_message.content, "\"")
        
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
            elif function_name == "buy_ticket":
                theater = json_message.get("theater")
                movie = json_message.get("movie")
                showtime = json_message.get("showtime")
                #message_history.append({"role": "system", "content": "Confirm ticket purchase for " + movie + " at " + showtime + " at " + theater + " ?"})
                result = buy_ticket(theater, movie, showtime)
            elif function_name == "confirm_ticket_purchase":
                theater = json_message.get("theater")
                movie = json_message.get("movie")
                showtime = json_message.get("showtime")


                #result = confirm_ticket_purchase(theater, movie, showtime)
            else:
                result = "Unknown result"
                
            message_history.append({"role": "system", "content": result})
            
            # print("result:", result)
            response_message = await generate_response(client, message_history, gen_kwargs)
            
            print("response_message: \"", response_message.content, "\"")

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
