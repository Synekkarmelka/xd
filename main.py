import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os

# Konfiguracja ID
ROLE_ID = 1386424048220766372
CHANNEL_ID = 1386424048270966820

class MandatModal(discord.ui.Modal, title='🚨 Wystawianie Mandatu Karnego'):
    # Okno prosi tylko o kwotę i powód, bo osoby wybraliśmy wcześniej
    kwota = discord.ui.TextInput(label='💰 Kwota Mandatu (zł)', placeholder='np. 500', min_length=1, max_length=10)
    powod = discord.ui.TextInput(label='📝 Powód Mandatu', style=discord.TextStyle.paragraph, placeholder='Opisz wykroczenie...', min_length=5)

    def __init__(self, wystawiajacy: discord.Member, otrzymujacy: discord.Member):
        super().__init__()
        self.wystawiajacy = wystawiajacy
        self.otrzymujacy = otrzymujacy

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Błąd: Nie odnaleziono kanału docelowego.", ephemeral=True)
            return

        # Tworzenie upiększonego Embedu
        embed = discord.Embed(
            title="🚨 MANDAT KARNY 🚨",
            description=f"Zostało zarejestrowane nowe wykroczenie drogowe/miejskie.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="👮 Funkcjonariusz Wystawiający", value=self.wystawiajacy.mention, inline=True)
        embed.add_field(name="👤 Obywatel Otrzymujący", value=self.otrzymujacy.mention, inline=True)
        embed.add_field(name="💸 Kwota Mandatu", value=f"**{self.kwota.value} zł**", inline=False)
        embed.add_field(name="📄 Powód", value=f"```{self.powod.value}```", inline=False)
        
        embed.set_footer(text="Komenda Stołeczna Policji")
        # Opcjonalnie: możesz dodać miniaturę (np. logo policji), jeśli masz link
        # embed.set_thumbnail(url="LINK_DO_OBRAZKA")

        # Wysyłka na kanał z prawdziwym pingiem w treści wiadomości
        await channel.send(content=f"Otrzymano mandat: {self.otrzymujacy.mention}", embed=embed)
        
        await interaction.response.send_message(f"✅ Mandat dla {self.otrzymujacy.display_name} został wysłany na kanał.", ephemeral=True)

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True # Wymagane do poprawnego czytania listy osób
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = Bot()

# 1. KOMENDA GŁÓWNA: /wystaw-mandat
@bot.tree.command(name="wystaw-mandat", description="Wystawia mandat (Wymagana rola Policji)")
@app_commands.describe(wystawiajacy="Wybierz funkcjonariusza", otrzymujacy="Wybierz osobę otrzymującą mandat")
async def wystaw_mandat(interaction: discord.Interaction, wystawiajacy: discord.Member, otrzymujacy: discord.Member):
    role = interaction.guild.get_role(ROLE_ID)
    
    # Sprawdzenie uprawnień
    if role not in interaction.user.roles:
        await interaction.response.send_message("❌ Nie masz uprawnień, aby użyć tej komendy!", ephemeral=True)
        return

    # Otwarcie okna formularza
    await interaction.response.send_modal(MandatModal(wystawiajacy, otrzymujacy))

# 2. KOMENDA DODATKOWA: /pomoc-policja
@bot.tree.command(name="pomoc-policja", description="Wyświetla instrukcję bota")
async def pomoc(interaction: discord.Interaction):
    embed = discord.Embed(title="Instrukcja Systemu Mandatowego", color=discord.Color.blue())
    embed.add_field(name="Użycie", value="/wystaw-mandat [osoba1] [osoba2]", inline=False)
    embed.set_footer(text="System Wspomagania Policji")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 3. KOMENDA DODATKOWA: /status
@bot.tree.command(name="status-bota", description="Sprawdza czy systemy bota są online")
async def status(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Systemy bota: **Online**\n🚨 Połączenie z bazą KSP: **Stabilne**", ephemeral=True)

token = os.getenv('DISCORD_TOKEN')
bot.run(token)
