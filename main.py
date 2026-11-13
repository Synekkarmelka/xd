import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os

# --- KONFIGURACJA ID ---
ID_ROLA_MANDAT = 1505624602083332100
ID_KANAL_MANDAT = 1505624603949662287

ID_ROLA_BAN = 1505624602125013018
ID_KANAL_BAN = 1505624606831022156

ID_ROLA_RP = 1505624602125013012
ID_KANAL_RP = 1505624605195370521

GIF_RP = "https://cdn.discordapp.com/attachments/1386424048774545419/1570821961087586436/standard_4.gif?ex=6af87d73&is=6af72bf3&hm=0856c9f3fc6bd2300973a112252e87a09d37e103c044071a3ee24052242905a8&"

# --- MODALE (OKNA WPISYWANIA) ---

class MandatModal(discord.ui.Modal, title='🚨 Wystawianie Mandatu'):
    kwota = discord.ui.TextInput(label='Kwota Mandatu (zł)', placeholder='np. 500')
    powod = discord.ui.TextInput(label='Powód Mandatu', style=discord.TextStyle.paragraph)

    def __init__(self, wystawiajacy, otrzymujacy):
        super().__init__()
        self.wystawiajacy = wystawiajacy
        self.otrzymujacy = otrzymujacy

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(ID_KANAL_MANDAT)
        embed = discord.Embed(title="🚨 Mandat Karny", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="👮 Funkcjonariusz", value=self.wystawiajacy.mention, inline=True)
        embed.add_field(name="👤 Obywatel", value=self.otrzymujacy.mention, inline=True)
        embed.add_field(name="💸 Kwota", value=f"**{self.kwota.value} zł**", inline=False)
        embed.add_field(name="📄 Powód", value=f"```{self.powod.value}```", inline=False)
        embed.set_footer(text="Komenda Stołeczna Policji")
        await channel.send(content=f"Otrzymano mandat: {self.otrzymujacy.mention}", embed=embed)
        await interaction.response.send_message("✅ Mandat został wystawiony.", ephemeral=True)

class BanModal(discord.ui.Modal, title='🔨 System Kar - Blokady'):
    nick_roblox = discord.ui.TextInput(label='Komu wystawiasz (Nick Roblox)', placeholder='Wpisz nick z gry...')
    za_co = discord.ui.TextInput(label='Za co?', style=discord.TextStyle.paragraph)
    ile_dni = discord.ui.TextInput(label='Ile dni?', placeholder='np. 7 / Na zawsze')
    dowody = discord.ui.TextInput(label='Dowody (Tak/Nie)', placeholder='Wpisz Tak lub Nie', required=False)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(ID_KANAL_BAN)
        embed = discord.Embed(title="🔨 Nowa Blokada", color=discord.Color.dark_red(), timestamp=datetime.now())
        embed.add_field(name="👤 Nick Roblox", value=f"**{self.nick_roblox.value}**", inline=False)
        embed.add_field(name="👮 Wystawił", value=interaction.user.mention, inline=False)
        embed.add_field(name="📝 Powód", value=f"```{self.za_co.value}```", inline=False)
        embed.add_field(name="⏳ Czas blokady", value=self.ile_dni.value, inline=True)
        embed.add_field(name="📸 Dowody", value=self.dowody.value or "Brak danych", inline=True)
        embed.set_footer(text="System Administracyjny VesperRP")
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Ban został zarejestrowany.", ephemeral=True)

class StartRpModal(discord.ui.Modal, title='🎮 Formularz Startu RP'):
    informacje = discord.ui.TextInput(label='Informacje', style=discord.TextStyle.paragraph, placeholder='Np. Takie poranne roleplay ;]')

    def __init__(self, kto_startuje):
        super().__init__()
        self.kto_startuje = kto_startuje

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(ID_KANAL_RP)
        embed = discord.Embed(title="🎭 ZAPRASZAM KAŻDEGO NA ROLEPLAY!", color=discord.Color.green())
        embed.add_field(name="👤 Startujący", value=self.kto_startuje.mention, inline=False)
        embed.add_field(name="🔑 KOD", value="`vesperp`", inline=True)
        embed.add_field(name="🏘️ Nazwa", value="`VesperRP`", inline=True)
        embed.add_field(name="ℹ️ Dodatkowe informacje", value=self.informacje.value, inline=False)
        embed.set_image(url=GIF_RP)
        
        await channel.send(content="@everyone", embed=embed)
        await interaction.response.send_message("✅ Sesja RP została wystartowana.", ephemeral=True)

# --- KLASA BOTA I KOMENDY ---

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

@bot.tree.command(name="wystaw-mandat", description="Wystawia mandat (Tylko Policja)")
async def wystaw_mandat(interaction: discord.Interaction, wystawiajacy: discord.Member, otrzymujacy: discord.Member):
    if interaction.guild.get_role(ID_ROLA_MANDAT) not in interaction.user.roles:
        return await interaction.response.send_message("❌ Nie masz uprawnień do tej komendy.", ephemeral=True)
    await interaction.response.send_modal(MandatModal(wystawiajacy, otrzymujacy))

@bot.tree.command(name="ban", description="Rejestruje bana gracza")
async def ban(interaction: discord.Interaction):
    if interaction.guild.get_role(ID_ROLA_BAN) not in interaction.user.roles:
        return await interaction.response.send_message("❌ Twoja ranga nie pozwala na użycie tej komendy.", ephemeral=True)
    await interaction.response.send_modal(BanModal())

@bot.tree.command(name="start-rp", description="Ogłasza start sesji RP")
async def start_rp(interaction: discord.Interaction, kto_startuje: discord.Member):
    if interaction.guild.get_role(ID_ROLA_RP) not in interaction.user.roles:
        return await interaction.response.send_message("❌ Nie masz uprawnień do startowania RP.", ephemeral=True)
    await interaction.response.send_modal(StartRpModal(kto_startuje))

token = os.getenv('DISCORD_TOKEN')
bot.run(token)
