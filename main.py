import os
import discord
from discord.ext import commands
import asyncio
from datetime import datetime

# Replace 'TOKEN' with your bot's token
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
        self.last_message_id = None
        self.cancel_requested = False

    async def cancel_deletion(self):
        if self.deletion_in_progress:
            self.cancel_requested = True
            return True
        return False

    async def delete_messages(self, channel, user, start_from_id=None):
        self.deletion_in_progress = True
        self.cancel_requested = False
        deleted_messages = 0
        processed_messages = 0
        start_time = datetime.now()

        try:
            before = discord.Object(id=start_from_id) if start_from_id else None
            search_start_logged = False

            while True:
                if self.cancel_requested:
                    print("Deletion process cancelled by user.")
                    break

                if not search_start_logged:
                    print(f"Started searching for messages before message ID: {before.id if before else 'the most recent message'}")
                    search_start_logged = True

                processed_messages += 1
                if processed_messages % 1000 == 0:
                    self.last_message_id = message.id
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

                before = message  # Continue from the last message processed

        finally:
            self.deletion_in_progress = False
            self.cancel_requested = False
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
async def d(ctx, user: discord.User, message_id: int = None):
    """Delete all messages of a specified user in the current channel.
    Optionally specify a message ID to start deletion from."""
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

    await deleter.delete_messages(ctx.channel, user, message_id)
    print(f"Deleted messages from {user.name}.")

# Error handling for command permissions
@d.error
async def d_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        print("You don't have permission to delete messages.")
    else:
        print(f"An error occurred: {error}")

@bot.command()
async def cancel(ctx):
    """Cancel the ongoing message deletion process."""
    if await deleter.cancel_deletion():
        print("Cancellation requested. The deletion process will stop soon.")
    else:
        print("No deletion process is currently running.")

# Run the bot
bot.run(TOKEN)