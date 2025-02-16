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
        # Prepare a prefix that includes guild and channel info
        prefix = f"[{channel.guild.name}/{channel.name}]"
        try:
            before = discord.Object(id=start_from_id) if start_from_id else None
            search_start_logged = False

            while True:
                # Check for cancellation before starting a new batch
                if self.cancel_requested:
                    print(f"{prefix} Deletion process cancelled before processing next batch.")
                    break

                last_message = None  # Track the last message processed in this batch

                async for message in channel.history(limit=1000, before=before):
                    # Check for cancellation mid-batch
                    if self.cancel_requested:
                        print(f"{prefix} Deletion process cancelled during batch processing.")
                        break

                    last_message = message
                    processed_messages += 1
                    if processed_messages % 1000 == 0:
                        self.last_message_id = message.id
                        print(f"{prefix} Viewed message ID: {message.id}, Author: {message.author}, Content: {message.content}")

                    if message.author == user:
                        try:
                            await message.delete()
                            deleted_messages += 1
                            print(f"{prefix} Deleted message ID: {message.id}, Author: {message.author}, Content: {message.content}")
                            await asyncio.sleep(1)  # Sleep to handle rate limits
                        except discord.errors.HTTPException as e:
                            if e.status == 429:
                                retry_after = e.response.headers.get('Retry-After')
                                if retry_after:
                                    retry_after = float(retry_after)
                                    print(f"{prefix} Rate limited. Retrying after {retry_after} seconds.")
                                    await asyncio.sleep(retry_after)
                            else:
                                print(f"{prefix} HTTPException: {e}")
                        except discord.errors.Forbidden:
                            print(f"{prefix} Forbidden: Cannot delete message in {channel.name}")
                        except discord.errors.NotFound:
                            print(f"{prefix} NotFound: Message already deleted in {channel.name}")
                        except discord.errors.DiscordException as e:
                            print(f"{prefix} DiscordException: {e}")
                        except Exception as e:
                            print(f"{prefix} Unexpected exception: {e}")

                # If cancellation was requested during the inner loop, break out
                if self.cancel_requested:
                    break

                # If no messages were retrieved in this batch, exit the loop
                if last_message is None:
                    break

                before = last_message  # Continue from the last message processed

        finally:
            self.deletion_in_progress = False
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"{prefix} Deletion process started at {start_time} and ended at {end_time}.")
            print(f"{prefix} Deleted {deleted_messages} messages from {user.name} in {duration:.2f} seconds.")

# Dictionary to keep track of deletion processes per channel
channel_deleters = {}

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def d(ctx, user: discord.User, message_id: int = None):
    """Delete all messages of a specified user in the current channel.
    Optionally specify a message ID to start deletion from."""
    prefix = f"[{ctx.guild.name}/{ctx.channel.name}]"
    deleter = channel_deleters.get(ctx.channel.id)
    if deleter and deleter.deletion_in_progress:
        print(f"{prefix} A deletion process is already in progress in this channel. Please wait until it finishes.")
        return

    deleter = MessageDeleter()
    channel_deleters[ctx.channel.id] = deleter

    try:
        await ctx.message.delete()  # Delete the command message
    except discord.errors.Forbidden:
        print(f"{prefix} Forbidden: Cannot delete the command message in {ctx.channel.name}")
    except discord.errors.NotFound:
        print(f"{prefix} NotFound: Command message already deleted in {ctx.channel.name}")
    except discord.errors.DiscordException as e:
        print(f"{prefix} DiscordException: {e}")
    except Exception as e:
        print(f"{prefix} Unexpected exception: {e}")

    await deleter.delete_messages(ctx.channel, user, message_id)
    print(f"{prefix} Completed deletion process for {user.name}.")

    # Clean up the deleter for this channel
    if ctx.channel.id in channel_deleters:
        del channel_deleters[ctx.channel.id]

@bot.command()
@commands.has_permissions(manage_messages=True)
async def cancel(ctx):
    """Cancel the current deletion process in this channel."""
    prefix = f"[{ctx.guild.name}/{ctx.channel.name}]"
    deleter = channel_deleters.get(ctx.channel.id)

    try:
        await ctx.message.delete()  # Delete the cancel command message
    except discord.errors.Forbidden:
        print(f"{prefix} Forbidden: Cannot delete the cancel command message in {ctx.channel.name}")
    except discord.errors.NotFound:
        print(f"{prefix} NotFound: Cancel command message already deleted in {ctx.channel.name}")
    except discord.errors.DiscordException as e:
        print(f"{prefix} DiscordException: {e}")
    except Exception as e:
        print(f"{prefix} Unexpected exception: {e}")

    if not deleter or not deleter.deletion_in_progress:
        print(f"{prefix} No deletion process is currently in progress in this channel.")
        return
    deleter.cancel_requested = True
    print(f"{prefix} Cancellation requested for the deletion process in this channel.")

@d.error
async def d_error(ctx, error):
    prefix = f"[{ctx.guild.name}/{ctx.channel.name}]"
    if isinstance(error, commands.MissingPermissions):
        print(f"{prefix} You don't have permission to delete messages.")
    else:
        print(f"{prefix} An error occurred: {error}")

# Run the bot
bot.run(TOKEN)
