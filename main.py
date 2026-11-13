import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os

# Konfiguracja ID
ROLE_ID = 1386424048220766372
CHANNEL_ID = 1386424048270966820

class MandatModal(discord.ui.Modal, title='Wystawianie Mandatu Karnego'):
    wystawiajacy = discord.ui.TextInput(label='Wystawiający', placeholder='np. @Jan_Kowalski')
    otrzymujacy = discord.ui.TextInput(label='Otrzymujący', placeholder='np. @Marek123')
    kwota = discord.ui.TextInput(label='Kwota Mandatu (zł)', placeholder='Sama liczba, np. 500')
    powod = discord.ui.TextInput(label='Powód Mandatu', style=discord.TextStyle.paragraph, placeholder='Wpisz powód wystawienia mandatu...')

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Błąd: Nie odnaleziono kanału docelowego.", ephemeral=True)
            return

        embed = discord.Embed(title="Mandat Karny", color=discord.Color.red())
        embed.add_field(name="Funkcjonariusz Wystawiający", value=self.wystawiajacy.value, inline=False)
        embed.add_field(name="Obywatel Otrzymujący", value=self.otrzymujacy.value, inline=False)
        embed.add_field(name="Kwota", value=f"{self.kwota.value} zł", inline=False)
        embed.add_field(name="Powód", value=self.powod.value, inline=False)
        embed.add_field(name="Data wystawienia", value=datetime.now().strftime("%d.%m.%Y"), inline=False)
        embed.set_footer(text="Komenda Stołeczna Policji")

        await channel.send(embed=embed)
        await interaction.response.send_message("Mandat został pomyślnie wystawiony i wysłany na kanał.", ephemeral=True)

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = Bot()

@bot.tree.command(name="wystaw-mandat", description="Otwiera okno wystawiania mandatu")
async def wystaw_mandat(interaction: discord.Interaction):
    # Sprawdzenie czy użytkownik ma wymaganą rolę
    role = interaction.guild.get_role(ROLE_ID)
    if role not in interaction.user.roles:
        await interaction.response.send_message("Nie posiadasz uprawnień (odpowiedniej roli) do użycia tej komendy.", ephemeral=True)
        return

    # Otwarcie okna (Modal)
    await interaction.response.send_modal(MandatModal())

# Pobieranie tokenu ze zmiennych środowiskowych
token = os.getenv('DISCORD_TOKEN')
bot.run(token)
