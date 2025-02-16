import os
import json
import discord
from discord.ext import commands
import asyncio
from datetime import datetime

# Replace 'YOUR_BOT_TOKEN' with your bot's token or set it in your environment variable TOKEN.
TOKEN = os.getenv('TOKEN')

# Create an instance of Intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Prefix for bot commands
bot = commands.Bot(command_prefix='!', intents=intents)

class MessageDeleter:
    def __init__(self):
        self.deletion_in_progress = False
        self.tracking_file = 'last_message_ids.json'
        self.tracking_data = self.load_tracking_data()

    def load_tracking_data(self):
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_tracking_data(self):
        with open(self.tracking_file, 'w') as f:
            json.dump(self.tracking_data, f)

    def save_last_message_id(self, channel_id, message_id):
        self.tracking_data[str(channel_id)] = message_id
        self.save_tracking_data()

    def get_last_message_id(self, channel_id):
        return self.tracking_data.get(str(channel_id))

    async def delete_messages(self, channel, user, start_message_id: int = None):
        self.deletion_in_progress = True
        deleted_messages = 0
        processed_messages = 0
        start_time = datetime.now()

        try:
            # Use the provided starting message ID if given; otherwise, try to load from tracking data.
            last_message_id = start_message_id if start_message_id is not None else self.get_last_message_id(channel.id)
            before = discord.Object(id=last_message_id) if last_message_id else None
            search_start_logged = False

            while True:
                messages = []
                async for message in channel.history(limit=1000, before=before):
                    messages.append(message)
                if not messages:
                    break

                for message in messages:
                    if not search_start_logged:
                        print(f"Started searching for messages before message ID: {before.id if before else 'the most recent message'} in channel {channel.name}")
                        search_start_logged = True
                    processed_messages += 1

                    # Update tracking every 100 messages processed
                    if processed_messages % 100 == 0:
                        self.save_last_message_id(channel.id, message.id)
                        print(f"Viewed message ID: {message.id}, Author: {message.author}, Content: {message.content}")

                    if message.author == user:
                        try:
                            await message.delete()
                            deleted_messages += 1
                            print(f"Deleted message ID: {message.id}, Author: {message.author}, Content: {message.content}")
                            await asyncio.sleep(1)  # Sleep to handle rate limits
                        except discord.errors.HTTPException as e:
                            if e.status == 429:
                                retry_after = e.response.headers.get('Retry-After')
                                if retry_after:
                                    retry_after = float(retry_after)
                                    print(f'Rate limited. Retrying after {retry_after} seconds.')
                                    await asyncio.sleep(retry_after)
                            else:
                                print(f'HTTPException: {e}')
                        except discord.errors.Forbidden:
                            print(f"Forbidden: Cannot delete message in {channel.name}")
                        except discord.errors.NotFound:
                            print(f"NotFound: Message already deleted in {channel.name}")
                        except discord.errors.DiscordException as e:
                            print(f'DiscordException: {e}')
                        except Exception as e:
                            print(f'Unexpected exception: {e}')

                # Continue with messages before the last one in the current batch
                before = discord.Object(id=messages[-1].id)

        finally:
            self.deletion_in_progress = False
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f'Deletion process started at {start_time} and ended at {end_time}.')
            print(f'Deleted {deleted_messages} messages from {user.name} in {duration:.2f} seconds.')

deleter = MessageDeleter()

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def d(ctx, user: discord.User, start_message_id: int = None):
    """
    Delete all messages of a specified user in the current channel.
    Optionally, provide a starting message ID to begin deletion from.
    Usage: !d @User [start_message_id]
    """
    if deleter.deletion_in_progress:
        print("A deletion process is already in progress. Please wait until it finishes.")
        return

    try:
        await ctx.message.delete()  # Delete the command message
    except discord.errors.Forbidden:
        print(f"Forbidden: Cannot delete the command message in {ctx.channel.name}")
    except discord.errors.NotFound:
        print(f"NotFound: Command message already deleted in {ctx.channel.name}")
    except discord.errors.DiscordException as e:
        print(f'DiscordException: {e}')
    except Exception as e:
        print(f'Unexpected exception: {e}')

    await deleter.delete_messages(ctx.channel, user, start_message_id)
    print(f"Deleted messages from {user.name}.")

@d.error
async def d_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        print("You don't have permission to delete messages.")
    else:
        print(f"An error occurred: {error}")

# Run the bot
bot.run(TOKEN)
