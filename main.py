import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import psycopg2

# --- KONFIGURACJA ID ---
ID_ROLA_MANDAT = 1505624602083332100
ID_KANAL_MANDAT = 1505624603949662287
EMOJI_KASA = "<a:kasa:1571615073976324196>"

ID_ROLA_BAN = 1505624602125013018
ID_KANAL_BAN = 1505624606831022156

ID_KANAL_ADMIN_USUN = 1570829927375184057

ID_KANAL_DOWOD_LOG = 1505624603949662285
ID_KANAL_POJAZD_LOG = 1505624603949662286

ID_ROLA_POSTAC_1 = 1505624602083332101
ID_ROLA_POSTAC_2 = 1505624601965760646

# Lista ID uprawnionych do ogłoszeń
ID_WLASCICIEL_OGLOS = [1130375423247790162, 1384107274754199573]

# --- POŁĄCZENIE Z BAZĄ DANYCH ---
def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db():
    conn = get_db_conn(); cur = conn.cursor()
    # Tabela postaci
    cur.execute('''CREATE TABLE IF NOT EXISTS characters (
        id SERIAL PRIMARY KEY, user_id BIGINT, name TEXT, roblox TEXT, 
        origin TEXT, age TEXT, dreams TEXT)''')
    # Tabela pojazdów
    cur.execute('''CREATE TABLE IF NOT EXISTS vehicles (
        id SERIAL PRIMARY KEY, char_id INTEGER REFERENCES characters(id) ON DELETE CASCADE, 
        brand TEXT, plate TEXT, color TEXT)''')
    # Tabela ekonomii
    cur.execute('''CREATE TABLE IF NOT EXISTS economy (
        user_id BIGINT PRIMARY KEY, wallet BIGINT DEFAULT 0, 
        last_collect TIMESTAMP, last_work TIMESTAMP)''')
    conn.commit(); cur.close(); conn.close()

# --- FUNKCJA ZARZĄDZANIA ROLAMI POSTACI ---
async def update_character_roles(member: discord.Member):
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT count(*) FROM characters WHERE user_id = %s", (member.id,))
    count = cur.fetchone()[0]
    cur.close(); conn.close()

    r1 = member.guild.get_role(ID_ROLA_POSTAC_1)
    r2 = member.guild.get_role(ID_ROLA_POSTAC_2)

    try:
        if count >= 1 and r1 and r1 not in member.roles:
            await member.add_roles(r1)
        elif count == 0 and r1 and r1 in member.roles:
            await member.remove_roles(r1)

        if count >= 2 and r2 and r2 not in member.roles:
            await member.add_roles(r2)
        elif count < 2 and r2 and r2 in member.roles:
            await member.remove_roles(r2)
    except:
        pass

# --- ADMIN VIEW (USUNIĘCIE POSTACI) ---
class AdminDeleteView(discord.ui.View):
    def __init__(self, user_id, char_id, char_name):
        super().__init__(timeout=None); self.user_id = user_id; self.char_id = char_id; self.char_name = char_name
    
    @discord.ui.button(label="Zaakceptuj", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM characters WHERE id = %s", (self.char_id,))
        conn.commit(); cur.close(); conn.close()
        
        try:
            member = interaction.guild.get_member(self.user_id) or await interaction.guild.fetch_member(self.user_id)
            if member: await update_character_roles(member)
        except: pass

        user = await interaction.client.fetch_user(self.user_id)
        try: await user.send(f"✅ Twój wniosek o usunięcie postaci **{self.char_name}** został zaakceptowany.")
        except: pass
        await interaction.response.edit_message(content=f"✅ Usunięto postać **{self.char_name}**.", view=None)

    @discord.ui.button(label="Odrzuć", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await interaction.client.fetch_user(self.user_id)
        try: await user.send(f"❌ Twój wniosek o usunięcie postaci **{self.char_name}** został odrzucony.")
        except: pass
        await interaction.response.edit_message(content=f"❌ Odrzucono wniosek o usunięcie **{self.char_name}**.", view=None)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        init_db()
        await self.tree.sync()

bot = MyBot()

# --- KOMENDA /OGLOS ---
@bot.tree.command(name="oglos", description="Tworzy oficjalne ogłoszenie")
async def oglos(interaction: discord.Interaction, kanal: discord.TextChannel, tresc: str):
    if interaction.user.id not in ID_WLASCICIEL_OGLOS:
        return await interaction.response.send_message("❌ Nie masz uprawnień do użycia tej komendy.", ephemeral=True)
    
    embed = discord.Embed(title="<a:alert:1571612218473058444> OGŁOSZENIE", description=tresc, color=discord.Color.gold(), timestamp=datetime.now())
    embed.set_footer(text=f"Ogłoszenie od: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    
    await kanal.send(embed=embed)
    await interaction.response.send_message("✅ Ogłoszenie wysłane.", ephemeral=True)

# --- KOMENDA /DOWOD ---
@bot.tree.command(name="dowod", description="Zarządzaj kartami postaci")
@app_commands.choices(opcja=[
    app_commands.Choice(name="Stwórz Postać", value="stworz"),
    app_commands.Choice(name="Sprawdź Postacie", value="sprawdz"),
    app_commands.Choice(name="Usuń Postać", value="usun"),
    app_commands.Choice(name="Sprawdź Postacie Obywatela", value="sprawdz_innego")
])
async def dowod(interaction: discord.Interaction, opcja: app_commands.Choice[str], obywatel: discord.Member = None):
    conn = get_db_conn(); cur = conn.cursor()
    
    if opcja.value in ["stworz", "sprawdz", "usun"] and obywatel is not None:
        cur.close(); conn.close()
        return await interaction.response.send_message("❌ Ta opcja dotyczy wyłącznie Ciebie!", ephemeral=True)
    
    target_user = obywatel if (opcja.value == "sprawdz_innego" and obywatel) else interaction.user
    
    if opcja.value == "stworz":
        cur.execute("SELECT count(*) FROM characters WHERE user_id = %s", (interaction.user.id,))
        if cur.fetchone()[0] >= 2:
            cur.close(); conn.close()
            return await interaction.response.send_message("❌ Masz już limit 2 postaci!", ephemeral=True)
        
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
                await update_character_roles(i.user)

                log_chan = i.guild.get_channel(ID_KANAL_DOWOD_LOG)
                if log_chan:
                    emb_log = discord.Embed(title="🪪 Nowy Dowód Osobisty", color=discord.Color.blue(), timestamp=datetime.now())
                    emb_log.add_field(name="Obywatel", value=i.user.mention, inline=False)
                    emb_log.add_field(name="Imię i Nazwisko", value=self.imie.value, inline=True)
                    await log_chan.send(embed=emb_log)
                await i.response.send_message("✅ Postać stworzona.", ephemeral=True)
        cur.close(); conn.close()
        await interaction.response.send_modal(CreateModal())

    elif opcja.value in ["sprawdz", "sprawdz_innego"]:
        cur.execute("SELECT name, roblox, origin, age, dreams FROM characters WHERE user_id = %s", (target_user.id,))
        rows = cur.fetchall()
        if not rows:
            cur.close(); conn.close()
            return await interaction.response.send_message(f"Brak dowodów dla {target_user.display_name}.", ephemeral=True)
        
        embed = discord.Embed(title=f"🪪 Dowody: {target_user.display_name}", color=discord.Color.blue())
        for r in rows:
            embed.add_field(name=f"👤 {r[0]}", value=f"**Roblox:** {r[1]}\n**Wiek:** {r[3]}", inline=False)
        cur.close(); conn.close()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    elif opcja.value == "usun":
        cur.execute("SELECT id, name FROM characters WHERE user_id = %s", (interaction.user.id,))
        rows = cur.fetchall()
        if not rows:
            cur.close(); conn.close()
            return await interaction.response.send_message("Nie masz postaci.", ephemeral=True)
        
        class DelSelect(discord.ui.Select):
            async def callback(self, i: discord.Interaction):
                cid, cname = self.values[0].split("|")
                class ReasonModal(discord.ui.Modal, title="Powód usunięcia"):
                    r = discord.ui.TextInput(label="Powód")
                    async def on_submit(self, i2: discord.Interaction):
                        chan = i2.guild.get_channel(ID_KANAL_ADMIN_USUN)
                        await chan.send(f"⚠️ Wniosek o usunięcie: {cname}", view=AdminDeleteView(i2.user.id, int(cid), cname))
                        await i2.response.send_message("Wysłano prośbę.", ephemeral=True)
                await i.response.send_modal(ReasonModal())

        v = discord.ui.View(); v.add_item(DelSelect(options=[discord.SelectOption(label=r[1], value=f"{r[0]}|{r[1]}") for r in rows]))
        cur.close(); conn.close()
        await interaction.response.send_message("Wybierz postać:", view=v, ephemeral=True)

# --- KOMENDA /POJAZD ---
@bot.tree.command(name="pojazd", description="Zarządzaj pojazdami")
@app_commands.choices(opcja=[
    app_commands.Choice(name="Rejestruj Pojazd", value="reg"),
    app_commands.Choice(name="Zmień Rejestracje/Kolor", value="edit"),
    app_commands.Choice(name="Sprawdź Pojazdy", value="list"),
    app_commands.Choice(name="Sprawdź Pojazdy Obywatela", value="list_innego")
])
async def pojazd(interaction: discord.Interaction, opcja: app_commands.Choice[str], obywatel: discord.Member = None):
    conn = get_db_conn(); cur = conn.cursor()
    
    if opcja.value in ["reg", "edit", "list"] and obywatel is not None:
        cur.close(); conn.close()
        return await interaction.response.send_message("❌ Ta opcja dotyczy Twoich pojazdów!", ephemeral=True)

    if opcja.value == "list_innego":
        if not obywatel:
            cur.close(); conn.close()
            return await interaction.response.send_message("❌ Wskaż obywatela!", ephemeral=True)
        cur.execute("SELECT id, name FROM characters WHERE user_id = %s", (obywatel.id,))
        chars = cur.fetchall()
        embed = discord.Embed(title=f"🚘 Pojazdy: {obywatel.display_name}", color=discord.Color.green())
        for cid, cname in chars:
            cur.execute("SELECT brand, plate, color FROM vehicles WHERE char_id = %s", (cid,))
            v_rows = cur.fetchall()
            v_txt = "\n".join([f"🚗 {v[0]} [{v[1]}]" for v in v_rows]) or "Brak aut."
            embed.add_field(name=f"Postać: {cname}", value=v_txt, inline=False)
        cur.close(); conn.close()
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    cur.execute("SELECT id, name FROM characters WHERE user_id = %s", (interaction.user.id,))
    chars = cur.fetchall()
    if not chars:
        cur.close(); conn.close()
        return await interaction.response.send_message("Najpierw stwórz postać!", ephemeral=True)

    if opcja.value == "reg":
        class RegModal(discord.ui.Modal, title="Rejestracja"):
            m = discord.ui.TextInput(label="Marka"); r = discord.ui.TextInput(label="Rejestracja"); k = discord.ui.TextInput(label="Kolor")
            def __init__(self, cid, cname): super().__init__(); self.cid = cid; self.cname = cname
            async def on_submit(self, i: discord.Interaction):
                c = get_db_conn(); cu = c.cursor()
                cu.execute("INSERT INTO vehicles (char_id, brand, plate, color) VALUES (%s,%s,%s,%s)", (self.cid, self.m.value, self.r.value, self.k.value))
                c.commit(); cu.close(); c.close()
                await i.response.send_message(f"✅ Zarejestrowano {self.m.value}.", ephemeral=True)
        
        class Sel(discord.ui.Select):
            async def callback(self, i: discord.Interaction):
                cid, cname = self.values[0].split("|")
                await i.response.send_modal(RegModal(int(cid), cname))
        v = discord.ui.View(); v.add_item(Sel(options=[discord.SelectOption(label=r[1], value=f"{r[0]}|{r[1]}") for r in chars]))
        cur.close(); conn.close()
        await interaction.response.send_message("Wybierz postać:", view=v, ephemeral=True)

    elif opcja.value == "edit":
        cur.execute("SELECT v.id, v.brand, v.plate FROM vehicles v JOIN characters c ON v.char_id = c.id WHERE c.user_id = %s", (interaction.user.id,))
        vehs = cur.fetchall()
        class EditModal(discord.ui.Modal, title="Edycja"):
            nr = discord.ui.TextInput(label="Nowa Rejestracja", required=False); nk = discord.ui.TextInput(label="Nowy Kolor", required=False)
            def __init__(self, vid): super().__init__(); self.vid = vid
            async def on_submit(self, i: discord.Interaction):
                c = get_db_conn(); cu = c.cursor()
                if self.nr.value: cu.execute("UPDATE vehicles SET plate = %s WHERE id = %s", (self.nr.value, self.vid))
                if self.nk.value: cu.execute("UPDATE vehicles SET color = %s WHERE id = %s", (self.nk.value, self.vid))
                c.commit(); cu.close(); c.close()
                await i.response.send_message("✅ Zaktualizowano.", ephemeral=True)
        class EditSel(discord.ui.Select):
            async def callback(self, i: discord.Interaction): await i.response.send_modal(EditModal(int(self.values[0])))
        v = discord.ui.View(); v.add_item(EditSel(options=[discord.SelectOption(label=f"{r[1]}", value=str(r[0])) for r in vehs]))
        cur.close(); conn.close()
        await interaction.response.send_message("Wybierz auto:", view=v, ephemeral=True)

    elif opcja.value == "list":
        embed = discord.Embed(title="🚘 Twoje Pojazdy", color=discord.Color.blue())
        for cid, cname in chars:
            cur.execute("SELECT brand, plate FROM vehicles WHERE char_id = %s", (cid,))
            v_rows = cur.fetchall()
            v_txt = "\n".join([f"🚗 {v[0]} [{v[1]}]" for v in v_rows]) or "Brak aut."
            embed.add_field(name=f"Postać: {cname}", value=v_txt, inline=False)
        cur.close(); conn.close()
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- KOMENDA /MANDAT ---
@bot.tree.command(name="mandat", description="Wystawia mandat obywatelowi")
async def mandat(interaction: discord.Interaction, wystawiajacy: discord.Member, otrzymujacy: discord.Member):
    if interaction.guild.get_role(ID_ROLA_MANDAT) not in interaction.user.roles: 
        return await interaction.response.send_message("❌ Brak rangi.", ephemeral=True)
    
    class MModal(discord.ui.Modal, title="Wystawianie Mandatu"):
        k = discord.ui.TextInput(label="Kwota"); p = discord.ui.TextInput(label="Powód", style=discord.TextStyle.paragraph)
        async def on_submit(self, i: discord.Interaction):
            try: kwota_val = int(self.k.value)
            except: return await i.response.send_message("❌ Nieprawidłowa kwota.", ephemeral=True)
            
            # Pobranie kasy z bazy
            conn = get_db_conn(); cur = conn.cursor()
            cur.execute("INSERT INTO economy (user_id, wallet) VALUES (%s, 0) ON CONFLICT DO NOTHING", (otrzymujacy.id,))
            cur.execute("UPDATE economy SET wallet = wallet - %s WHERE user_id = %s", (kwota_val, otrzymujacy.id))
            conn.commit(); cur.close(); conn.close()
            
            e = discord.Embed(title="<a:Alert:1571612218473058444> Karny", color=discord.Color.red(), timestamp=datetime.now())
            e.add_field(name="Funkcjonariusz", value=wystawiajacy.mention, inline=True)
            e.add_field(name="Obywatel", value=otrzymujacy.mention, inline=True)
            e.add_field(name="Kwota", value=f"{kwota_val} ZŁ", inline=False)
            e.add_field(name="Powód", value=f"```{self.p.value}```", inline=False)
            e.set_footer(text="Komenda Stołeczna Policji")
            await i.guild.get_channel(ID_KANAL_MANDAT).send(content=f"{otrzymujacy.mention}", embed=e)
            await i.response.send_message(f"✅ Wystawiono mandat na {kwota_val} ZŁ. Środki pobrane.", ephemeral=True)
    await interaction.response.send_modal(MModal())

@bot.tree.command(name="ban")
async def ban(interaction: discord.Interaction):
    if interaction.guild.get_role(ID_ROLA_BAN) not in interaction.user.roles: return await interaction.response.send_message("Brak rangi.", ephemeral=True)
    class BModal(discord.ui.Modal, title="Ban"):
        n = discord.ui.TextInput(label="Nick Roblox"); z = discord.ui.TextInput(label="Za co"); i = discord.ui.TextInput(label="Ile dni"); d = discord.ui.TextInput(label="Dowody", required=False)
        async def on_submit(self, i_b: discord.Interaction):
            e = discord.Embed(title="🔨 Nowa Blokada", color=discord.Color.dark_red(), timestamp=datetime.now())
            e.add_field(name="👤 Roblox", value=self.n.value); e.add_field(name="👮 Wystawił", value=i_b.user.mention); e.add_field(name="⏳ Czas", value=self.i.value)
            await i_b.guild.get_channel(ID_KANAL_BAN).send(embed=e)
            await i_b.response.send_message("Zbanowano.", ephemeral=True)
    await interaction.response.send_modal(BModal())

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name="Gram na Vesper RP"))

bot.run(os.getenv("DISCORD_TOKEN"))
