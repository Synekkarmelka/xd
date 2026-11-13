import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import psycopg2

# --- KONFIGURACJA ID ---
ID_ROLA_MANDAT = 1386424048220766372
ID_KANAL_MANDAT = 1386424048270966820
ID_ROLA_BAN = 1386424048220766371
ID_KANAL_BAN = 1386424048774545418
ID_ROLA_RP = 1386424048220766374
ID_KANAL_RP = 1386424048774545419
ID_KANAL_ADMIN_USUN = 1505624605195370521
GIF_RP = "https://cdn.discordapp.com/attachments/1386424048774545419/1570821961087586436/standard_4.gif"

# --- POŁĄCZENIE Z BAZĄ DANYCH ---
def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS characters (
        id SERIAL PRIMARY KEY, user_id BIGINT, name TEXT, roblox TEXT, 
        origin TEXT, age TEXT, dreams TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS vehicles (
        id SERIAL PRIMARY KEY, char_id INTEGER REFERENCES characters(id) ON DELETE CASCADE, 
        brand TEXT, plate TEXT, color TEXT)''')
    conn.commit()
    cur.close()
    conn.close()

# --- SYSTEM AKCEPTACJI USUNIĘCIA POSTACI ---
class AdminDeleteView(discord.ui.View):
    def __init__(self, user_id, char_id, char_name):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.char_id = char_id
        self.char_name = char_name

    @discord.ui.button(label="Zaakceptuj Usunięcie", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM characters WHERE id = %s", (self.char_id,))
        conn.commit(); cur.close(); conn.close()
        
        user = await interaction.client.fetch_user(self.user_id)
        try:
            await user.send(f"✅ Twój wniosek o usunięcie postaci **{self.char_name}** został zaakceptowany przez {interaction.user.display_name}. Możesz teraz stworzyć nową postać.")
        except: pass
        await interaction.response.edit_message(content=f"✅ Postać **{self.char_name}** gracza <@{self.user_id}> została usunięta.", view=None)

    @discord.ui.button(label="Odrzuć", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await interaction.client.fetch_user(self.user_id)
        try:
            await user.send(f"❌ Twój wniosek o usunięcie postaci **{self.char_name}** został odrzucony przez {interaction.user.display_name}.")
        except: pass
        await interaction.response.edit_message(content=f"❌ Odrzucono prośbę o usunięcie postaci **{self.char_name}**.", view=None)

# --- KLASA BOTA ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        init_db()
        await self.tree.sync()

bot = MyBot()

# --- KOMENDA /DOWOD ---
@bot.tree.command(name="dowod", description="Zarządzaj swoją kartą postaci")
@app_commands.choices(opcja=[
    app_commands.Choice(name="Stwórz Postać", value="stworz"),
    app_commands.Choice(name="Sprawdź Postacie", value="sprawdz"),
    app_commands.Choice(name="Usuń Postać", value="usun")
])
async def dowod(interaction: discord.Interaction, opcja: app_commands.Choice[str]):
    conn = get_db_conn(); cur = conn.cursor()
    
    if opcja.value == "stworz":
        cur.execute("SELECT count(*) FROM characters WHERE user_id = %s", (interaction.user.id,))
        if cur.fetchone()[0] >= 2:
            return await interaction.response.send_message("❌ Masz już 2 postacie! Usuń jedną, aby stworzyć nową.", ephemeral=True)
        
        class CreateModal(discord.ui.Modal, title="Tworzenie Postaci"):
            imie = discord.ui.TextInput(label="Imię I nazwisko")
            roblox = discord.ui.TextInput(label="Nick Roblox")
            poch = discord.ui.TextInput(label="Pochodzenie")
            wiek = discord.ui.TextInput(label="Wiek")
            marz = discord.ui.TextInput(label="Marzenia", style=discord.TextStyle.paragraph)

            async def on_submit(self, i: discord.Interaction):
                c = get_db_conn(); cu = c.cursor()
                cu.execute("INSERT INTO characters (user_id, name, roblox, origin, age, dreams) VALUES (%s,%s,%s,%s,%s,%s)",
                           (i.user.id, self.imie.value, self.roblox.value, self.poch.value, self.wiek.value, self.marz.value))
                c.commit(); cu.close(); c.close()
                embed = discord.Embed(title="✅ Postać Stworzona", color=discord.Color.blue())
                embed.add_field(name="Imię i Nazwisko", value=self.imie.value)
                embed.add_field(name="Nick Roblox", value=self.roblox.value)
                await i.response.send_message(embed=embed, ephemeral=True)
        await interaction.response.send_modal(CreateModal())

    elif opcja.value == "sprawdz":
        cur.execute("SELECT name, roblox, origin FROM characters WHERE user_id = %s", (interaction.user.id,))
        rows = cur.fetchall()
        if not rows: return await interaction.response.send_message("Brak stworzonych postaci.", ephemeral=True)
        txt = "\n".join([f"👤 **{r[0]}** (Roblox: {r[1]})" for r in rows])
        await interaction.response.send_message(f"Twoje postacie:\n{txt}", ephemeral=True)

    elif opcja.value == "usun":
        cur.execute("SELECT id, name FROM characters WHERE user_id = %s", (interaction.user.id,))
        rows = cur.fetchall()
        if not rows: return await interaction.response.send_message("Nie masz postaci do usunięcia.", ephemeral=True)
        
        class DeleteSelect(discord.ui.Select):
            async def callback(self, i: discord.Interaction):
                cid, cname = self.values[0].split("|")
                class ReasonModal(discord.ui.Modal, title="Powód usunięcia"):
                    r = discord.ui.TextInput(label="Czemu chcesz usunąć postać?")
                    async def on_submit(self, i2: discord.Interaction):
                        chan = i2.guild.get_channel(ID_KANAL_ADMIN_USUN)
                        await chan.send(f"⚠️ **Wniosek o usunięcie postaci**\nGracz: {i2.user.mention}\nPostać: {cname}\nPowód: {self.r.value}", 
                                        view=AdminDeleteView(i2.user.id, int(cid), cname))
                        await i2.response.send_message("Wniosek wysłany do administracji.", ephemeral=True)
                await i.response.send_modal(ReasonModal())

        view = discord.ui.View(); view.add_item(DeleteSelect(options=[discord.SelectOption(label=r[1], value=f"{r[0]}|{r[1]}") for r in rows]))
        await interaction.response.send_message("Wybierz postać do usunięcia:", view=view, ephemeral=True)
    cur.close(); conn.close()

# --- KOMENDA /POJAZD ---
@bot.tree.command(name="pojazd", description="Zarządzaj swoimi pojazdami")
@app_commands.choices(opcja=[
    app_commands.Choice(name="Rejestruj Pojazd", value="reg"),
    app_commands.Choice(name="Zmień Rejestracje/Kolor", value="edit"),
    app_commands.Choice(name="Sprawdź Pojazdy", value="list")
])
async def pojazd(interaction: discord.Interaction, opcja: app_commands.Choice[str]):
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM characters WHERE user_id = %s", (interaction.user.id,))
    chars = cur.fetchall()
    if not chars: return await interaction.response.send_message("Musisz najpierw stworzyć postać!", ephemeral=True)

    if opcja.value == "reg":
        class RegModal(discord.ui.Modal, title="Rejestracja Pojazdu"):
            m = discord.ui.TextInput(label="Marka"); r = discord.ui.TextInput(label="Rejestracja"); k = discord.ui.TextInput(label="Kolor")
            def __init__(self, cid): super().__init__(); self.cid = cid
            async def on_submit(self, i: discord.Interaction):
                c = get_db_conn(); cu = c.cursor()
                cu.execute("INSERT INTO vehicles (char_id, brand, plate, color) VALUES (%s,%s,%s,%s)", (self.cid, self.m.value, self.r.value, self.k.value))
                c.commit(); cu.close(); c.close()
                await i.response.send_message(f"✅ Zarejestrowano pojazd {self.m.value}!", ephemeral=True)
        
        class CharSel(discord.ui.Select):
            async def callback(self, i: discord.Interaction): await i.response.send_modal(RegModal(int(self.values[0])))
        v = discord.ui.View(); v.add_item(CharSel(options=[discord.SelectOption(label=r[1], value=str(r[0])) for r in chars]))
        await interaction.response.send_message("Wybierz postać:", view=v, ephemeral=True)

    elif opcja.value == "list":
        embed = discord.Embed(title="🚘 Twoje Pojazdy", color=discord.Color.gold())
        for cid, cname in chars:
            cur.execute("SELECT brand, plate, color FROM vehicles WHERE char_id = %s", (cid,))
            v_rows = cur.fetchall()
            v_txt = "\n".join([f"🚗 {v[0]} [{v[1]}] - {v[2]}" for v in v_rows]) if v_rows else "Brak aut."
            embed.add_field(name=f"Postać: {cname}", value=v_txt, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    cur.close(); conn.close()

# --- KOMENDY POLICYJNE I ADMINISTRACYJNE (MANDAT, BAN, START) ---
@bot.tree.command(name="wystaw-mandat")
async def mandat(interaction: discord.Interaction, wystawiajacy: discord.Member, otrzymujacy: discord.Member):
    if interaction.guild.get_role(ID_ROLA_MANDAT) not in interaction.user.roles: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    class MModal(discord.ui.Modal, title="Wystawianie Mandatu"):
        k = discord.ui.TextInput(label="Kwota (zł)"); p = discord.ui.TextInput(label="Powód", style=discord.TextStyle.paragraph)
        async def on_submit(self, i: discord.Interaction):
            e = discord.Embed(title="🚨 Mandat Karny", color=discord.Color.red(), timestamp=datetime.now())
            e.add_field(name="👮 Funkcjonariusz", value=wystawiajacy.mention, inline=True)
            e.add_field(name="👤 Obywatel", value=otrzymujacy.mention, inline=True)
            e.add_field(name="💸 Kwota", value=f"{self.k.value} zł", inline=False)
            e.add_field(name="📄 Powód", value=f"```{self.p.value}```", inline=False)
            e.set_footer(text="Komenda Stołeczna Policji")
            await i.guild.get_channel(ID_KANAL_MANDAT).send(content=f"Otrzymano mandat: {otrzymujacy.mention}", embed=e)
            await i.response.send_message("Wysłano.", ephemeral=True)
    await interaction.response.send_modal(MModal())

@bot.tree.command(name="ban")
async def ban(interaction: discord.Interaction):
    if interaction.guild.get_role(ID_ROLA_BAN) not in interaction.user.roles: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    class BModal(discord.ui.Modal, title="System Banów"):
        n = discord.ui.TextInput(label="Nick Roblox"); z = discord.ui.TextInput(label="Za co"); i = discord.ui.TextInput(label="Ile dni"); d = discord.ui.TextInput(label="Dowody (Tak/Nie)", required=False)
        async def on_submit(self, i: discord.Interaction):
            e = discord.Embed(title="🔨 Nowa Blokada", color=discord.Color.dark_red(), timestamp=datetime.now())
            e.add_field(name="👤 Nick Roblox", value=self.n.value); e.add_field(name="👮 Wystawił", value=i.user.mention)
            e.add_field(name="📝 Powód", value=self.z.value); e.add_field(name="⏳ Czas", value=self.i.value)
            await i.guild.get_channel(ID_KANAL_BAN).send(embed=e)
            await i.response.send_message("Zbanowano.", ephemeral=True)
    await interaction.response.send_modal(BModal())

@bot.tree.command(name="start-rp")
async def start(interaction: discord.Interaction, kto_startuje: discord.Member):
    if interaction.guild.get_role(ID_ROLA_RP) not in interaction.user.roles: return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
    class SModal(discord.ui.Modal, title="Start RP"):
        inf = discord.ui.TextInput(label="Informacje", placeholder="Np. Takie poranne roleplay ;]")
        async def on_submit(self, i: discord.Interaction):
            e = discord.Embed(title="🎭 ZAPRASZAM KAŻDEGO NA ROLEPLAY!", color=discord.Color.green())
            e.add_field(name="👤 Startujący", value=kto_startuje.mention); e.add_field(name="🔑 KOD", value="`vesperp`")
            e.add_field(name="🏘️ Nazwa", value="`VesperRP`")
            e.add_field(name="ℹ️ Info", value=self.inf.value)
            e.set_image(url=GIF_RP)
            await i.guild.get_channel(ID_KANAL_RP).send(content="@everyone", embed=e)
            await i.response.send_message("Wystartowano RP.", ephemeral=True)
    await interaction.response.send_modal(SModal())

bot.run(os.getenv("DISCORD_TOKEN"))
