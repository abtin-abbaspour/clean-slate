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
        self.cancel_requested = False  # Cancellation flag
        self.last_message_id = None  # Store ID in memory instead of file

    async def delete_messages(self, channel, user, start_from_id=None):
        self.deletion_in_progress = True
        self.cancel_requested = False  # Reset cancellation flag at start
        deleted_messages = 0
        processed_messages = 0
        start_time = datetime.now()

        try:
            before = discord.Object(id=start_from_id) if start_from_id else None
            search_start_logged = False

            while True:
                # Check for cancellation before processing a new batch
                if self.cancel_requested:
                    print("Deletion process cancelled before processing next batch.")
                    break

                last_message = None  # Track the last message processed in this batch

                async for message in channel.history(limit=1000, before=before):
                    # Check for cancellation mid-batch
                    if self.cancel_requested:
                        print("Deletion process cancelled during batch processing.")
                        break

                    last_message = message
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

                # If cancellation was requested during the inner loop, exit immediately
                if self.cancel_requested:
                    break

                # If no messages were retrieved, exit the loop
                if last_message is None:
                    break

                before = last_message  # Continue from the last message processed

        finally:
            self.deletion_in_progress = False
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f'Deletion process started at {start_time} and ended at {end_time}.')
            print(f'Deleted {deleted_messages} messages from {user.name} in {duration:.2f} seconds.')

# Dictionary to keep track of deletion processes per channel
channel_deleters = {}

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def d(ctx, user: discord.User, message_id: int = None):
    """Delete all messages of a specified user in the current channel.
    Optionally specify a message ID to start deletion from."""
    # Use a per-channel deleter instance to allow simultaneous deletions across channels/servers
    deleter = channel_deleters.get(ctx.channel.id)
    if deleter and deleter.deletion_in_progress:
        print("A deletion process is already in progress in this channel. Please wait until it finishes.")
        return

    deleter = MessageDeleter()
    channel_deleters[ctx.channel.id] = deleter

    try:
        await ctx.message.delete()  # Delete the command message
    except discord.errors.Forbidden:
        print(f"Forbidden: Cannot delete the command message in {ctx.channel.name}")
    except discord.errors.NotFound:
        print(f"NotFound: Command message already deleted in {ctx.channel.name}")
    except discord.errors.DiscordException as e:
        print(f"DiscordException: {e}")
    except Exception as e:
        print(f"Unexpected exception: {e}")

    await deleter.delete_messages(ctx.channel, user, message_id)
    print(f"Deleted messages from {user.name}.")

    # Remove the deleter once the deletion process is complete
    if ctx.channel.id in channel_deleters:
        del channel_deleters[ctx.channel.id]

@bot.command()
@commands.has_permissions(manage_messages=True)
async def cancel(ctx):
    """Cancel the current deletion process in this channel."""
    deleter = channel_deleters.get(ctx.channel.id)
    if not deleter or not deleter.deletion_in_progress:
        await ctx.send("No deletion process is currently in progress in this channel.")
        return
    deleter.cancel_requested = True
    await ctx.send("Cancellation requested for the deletion process in this channel.")

# Error handling for command permissions
@d.error
async def d_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        print("You don't have permission to delete messages.")
    else:
        print(f"An error occurred: {error}")

# Run the bot
bot.run(TOKEN)