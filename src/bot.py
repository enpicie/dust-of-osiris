import traceback
from aws_services import AWSServices

import commands.command_map as command_map
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def process_bot_command(event_body: dict, aws_services: AWSServices) -> dict:
    """Dispatch a Discord slash command interaction to its registered handler.

    :param event_body: Parsed Discord interaction payload.
    :param aws_services: Shared AWS service clients.
    :return: The interaction response as a dict.
    """
    if "data" not in event_body:
        raise KeyError("No field 'data'. This is not a valid Discord Slash Command message.")

    event = DiscordEvent(event_body)
    command_name = event.get_command_name()

    command = command_map.command_map.get(command_name)
    if command is None:
        raise ValueError(f"No command registered for {command_name}")

    command_function = command["function"]
    print(f"[bot] command={command_name} server={event.get_server_id()} user={event.get_user_id()}")
    try:
        message = command_function(event, aws_services)
    except ValueError as e:
        print(f"[bot] ERROR ValueError | command={command_name} | {e}")
        print(f"[bot] {traceback.format_exc()}")
        message = ResponseMessage(content=str(e))
    except Exception as e:
        print(f"[bot] ERROR {type(e).__name__} | command={command_name} | {e}")
        print(f"[bot] {traceback.format_exc()}")
        message = ResponseMessage.get_error_message()
    if message:
        print(f"[bot] command={command_name} -> ok")
        return message.to_dict()

    raise RuntimeError(f"Error processing command '{command_name}': did not return a message.")

def process_input_autocomplete(event_body: dict, aws_services: AWSServices) -> dict:
    """Dispatch an autocomplete interaction to the focused option's handler.

    :param event_body: Parsed Discord interaction payload.
    :param aws_services: Shared AWS service clients.
    :return: The autocomplete choices response as a dict.
    """
    if "data" not in event_body:
        raise KeyError("No field 'data'. This is not a valid Discord Slash Command message.")

    options = event_body["data"].get("options", [])
    focused_option = next((o for o in options if o.get("focused")), None)
    if focused_option is None:
        raise KeyError("No focused option found in autocomplete interaction.")

    command_name = event_body["data"]["name"]
    command = command_map.command_map.get(command_name)
    if command is None:
        raise ValueError(f"No command registered for {command_name}")

    param = next((p for p in command["params"] if p.name == focused_option["name"]), None)
    if param is None or param.autocomplete_handler is None:
        raise ValueError(f"No autocomplete handler for option '{focused_option['name']}' on command '{command_name}'")

    event = DiscordEvent(event_body)
    response = param.autocomplete_handler(event, aws_services)
    return response.to_dict()
