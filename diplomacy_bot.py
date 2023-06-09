import discord
from discord.ext import commands
from diplomacy import Game
from diplomacy.engine.renderer import Renderer
import cairosvg
import io
import os
from PIL import Image
import random
from io import BytesIO
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM, shapes

intents = discord.Intents.all()
intents.typing = False
intents.presences = False
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def convert_svg_to_png(svg_data, scale=2):
    svg_io = BytesIO(svg_data.encode('utf-8'))
    drawing = svg2rlg(svg_io)

    drawing.scale(scale, scale)
    scaled_drawing = shapes.Drawing(drawing.width * scale, drawing.height * scale)
    scaled_drawing.add(drawing)

    png_io = BytesIO()
    renderPM.drawToFile(scaled_drawing, png_io, fmt='PNG')
    png_io.seek(0)
    return png_io


async def create_channels(guild):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    bot_announcement = discord.utils.get(guild.text_channels, name="bot-announcement")
    if not bot_announcement:
        bot_announcement = await guild.create_text_channel("bot-announcement", overwrites=overwrites)

    bot_commands = discord.utils.get(guild.text_channels, name="bot-commands")
    if not bot_commands:
        bot_commands = await guild.create_text_channel("bot-commands", overwrites=overwrites)

    return bot_announcement, bot_commands


async def send_map_image(player, game):
    buffer = io.BytesIO()
    renderer = Renderer(game)
    svg_data = renderer.render(incl_abbrev=True)
    buffer = convert_svg_to_png(svg_data)
    await player.send(file=discord.File(fp=buffer, filename="map.png"))

    power = powers_assigned[players.index(player)]
    units = game.get_units(power)
    possible_orders = game.get_all_possible_orders()
    possible_orders = {unit: orders for unit, orders in possible_orders.items() if any(unit in u for u in units)}
    await player.send("Possible orders for {}: {}".format(power, ', '.join(f"{unit}: {', '.join(orders)}" for unit, orders in possible_orders.items())))



game = None
players = []
orders = {}
powers_assigned = []


@bot.command(name="start")
async def start(ctx):
    global game, players, orders
    
    if ctx.channel.name != "bot-commands":
        await ctx.send("Please start and join the game from the bot-commands channel.")
        return

    if len(players) < 1:
        await ctx.send("There must be at least 3 players to start the game.")
        return
    
    game = Game()
    
    for player in players:
        orders[player.id] = []
        await send_map_image(player, game)

    await ctx.send("The game has started!")
    bot_announcement, _ = await create_channels(ctx.guild)
    await bot_announcement.send("A new game of Diplomacy has started!")

    for player in players:
        orders[player.id] = None
        await send_map_image(player, game)


@bot.command(name="join")
async def join(ctx, power_choice: str = None):
    global players, powers_assigned
    if ctx.channel.name != "bot-commands":
        await ctx.send("Please start and join the game from the bot-commands channel.")
        return

    if ctx.author in players:
        await ctx.send("You have already joined the game.")
        return

    available_powers = [power for power in Game().powers.keys() if power not in powers_assigned]

    if power_choice and power_choice.capitalize() in available_powers:
        power = power_choice.capitalize()
    elif power_choice and power_choice.capitalize() not in available_powers:
        await ctx.send(f"{power_choice.capitalize()} is not an available power. Please choose from the available powers: {', '.join(available_powers)}")
        return
    else:
        power = random.choice(available_powers)

    players.append(ctx.author)
    powers_assigned.append(power)
    bot_announcement_channel = discord.utils.get(ctx.guild.channels, name="bot-announcement")
    await bot_announcement_channel.send(f"{ctx.author.mention} has joined the game as {power}.")


@bot.command(name="order")
async def order(ctx, *, order_text):
    global orders, game

    # Get the first guild the author is a member of
    guild = None
    for g in bot.guilds:
        if g.get_member(ctx.author.id):
            guild = g
            break

    if guild is None:
        await ctx.send("You must be a member of a server where the bot is present.")
        return

    if ctx.author.id not in orders:
        await ctx.send("You are not in the current game.")
        return

    power = powers_assigned[players.index(ctx.author)]
    units = game.get_units(power)
    possible_orders = game.get_all_possible_orders()
    possible_orders = {unit: orders for unit, orders in possible_orders.items() if any(unit in u for u in units)}

    if order_text not in sum(possible_orders.values(), []):
        await ctx.send("Invalid order. Please provide a valid order.")
        return

    if ctx.author.id not in orders or orders[ctx.author.id] is None:
        orders[ctx.author.id] = [order_text]
    else:
        orders[ctx.author.id].append(order_text)

    remaining_orders = [unit for unit, unit_orders in possible_orders.items() if all(order not in orders[ctx.author.id] for order in unit_orders)]
    if remaining_orders:
        await ctx.send(f"Order accepted. You still need to issue orders for the following units: {', '.join(remaining_orders)}")
    else:
        all_orders_complete = all(o is not None for o in orders.values())
        if all_orders_complete:
            for player_id, player_orders in orders.items():
                power_name = powers_assigned[players.index(bot.get_user(player_id))]
                game.set_orders(power_name, player_orders)

            game.process()
            for player_id in orders:
                orders[player_id] = None
            bot_announcement, _ = await create_channels(guild)
            await bot_announcement.send("The turn has advanced!")
            for player in players:
                await send_map_image(player, game)

            guild = players[0].guild
            bot_announcement_channel = discord.utils.get(guild.channels, name="bot-announcement")
            if bot_announcement_channel is not None:
                await send_map_image(bot_announcement_channel, game)




@bot.command(name="showmap")
async def showmap(ctx):
    if ctx.author not in players:
        await ctx.send("You are not in the current game.")
    else:
        await send_map_image(ctx.author, game)


@bot.command(name="endgame")
async def endgame(ctx):
    global game, players, orders, powers_assigned
    if ctx.author not in players:
        await ctx.send("You are not in the current game.")
        return

    if not hasattr(endgame, "votes"):
        endgame.votes = set()

    endgame.votes.add(ctx.author)

    if len(endgame.votes) > len(players) / 2:
        game = None
        players = []
        orders = {}
        powers_assigned = []
        del endgame.votes
        await ctx.send("The game has ended.")
        bot_announcement, _ = await create_channels(ctx.guild)
        await bot_announcement.send("The game of Diplomacy has ended!")
    else:
        votes_needed = (len(players) // 2) + 1 - len(endgame.votes)
        await ctx.send(f"{ctx.author.name} has voted to end the game. {votes_needed} more vote(s) needed to end the game.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if (hasattr(message.channel, 'name') and message.channel.name == "bot-commands") or isinstance(message.channel, discord.DMChannel):
        await bot.process_commands(message)


@bot.command(name="showhelp")
async def show_help(ctx):
    help_text = """
**Diplomacy Bot Commands:**

- `!join`: Join the current Diplomacy game.
- `!start`: Start the game when at least 3 players have joined.
- `!order <order>`: Submit an order in the format "Power Unit Type (start) - (end)". For example: "Russia A Moscow - Warsaw".
- `!showmap`: Receive the current game map via a private message.
- `!endgame`: Vote to end the current game. The game will end if more than half the players vote.
- `!showhelp`: Display this help message.
    """
    await ctx.send(help_text)


@bot.event
async def on_guild_join(guild):
    await create_channels(guild)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    for guild in bot.guilds:
        await create_channels(guild)


from settings import TOKEN
bot.run(TOKEN)

