require('dotenv').config();
const fs = require('fs');
const {
  Client, GatewayIntentBits, Partials, REST, Routes,
  SlashCommandBuilder, PermissionFlagsBits, ComponentType,
  ActionRowBuilder, ButtonBuilder, ButtonStyle,
  ModalBuilder, TextInputBuilder, TextInputStyle,
  StringSelectMenuBuilder, RoleSelectMenuBuilder,
  EmbedBuilder,
} = require('discord.js');

const GUILD_ID = process.env.GUILD_ID || '1235851616586825790';
const APPS_CHANNEL_ID = process.env.APPLICATIONS_CHANNEL_ID || '1565802903539552357';
const DATA_PATH = process.env.DATA_PATH || './data.json';
const SESSION_MS = 30 * 60 * 1000; // 30 minutes
const HL2 = 0xfb7c0d; // Half-Life 2 orange

// ---------------- STORAGE (persists across restarts) ----------------
function loadData() {
  try { return JSON.parse(fs.readFileSync(DATA_PATH, 'utf8')); }
  catch { return { applications: {}, submissions: {} }; }
}
let data = loadData();
function saveData() {
  const tmp = DATA_PATH + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, DATA_PATH); // atomic write, no corruption on crash
}
setInterval(saveData, 30_000); // autosave every 30s

// ---------------- HELPERS ----------------
const hl2 = (title, desc) => new EmbedBuilder()
  .setColor(HL2)
  .setTitle(title)
  .setDescription(desc)
  .setFooter({ text: 'CITY 17 // APPLICATION TERMINAL v2.3' })
  .setTimestamp();

const fmt = (ms) => {
  const t = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(t / 60)}m ${t % 60}s`;
};

// in-memory: setup wizards + active DM sessions (sessions die on restart by design)
const setups = new Map();
const sessions = new Map();

// ---------------- CLIENT ----------------
const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.DirectMessages],
  partials: [Partials.Channel],
});

const commands = [
  new SlashCommandBuilder().setName('setup-application')
    .setDescription('[ADMIN] Create a new application form')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('name').setDescription('Application name (e.g. Security Officer)').setRequired(true).setMaxLength(60))
    .addIntegerOption(o => o.setName('questions').setDescription('How many questions? (1-20)').setRequired(true).setMinValue(1).setMaxValue(20)),
  new SlashCommandBuilder().setName('manage-applications')
    .setDescription('[ADMIN] Open/close applications and set the reviewer role')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('send-panel')
    .setDescription('[ADMIN] Post the applications browser panel in this channel')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
];

// ---------------- SETUP WIZARD ----------------
function setupRows(userId) {
  const st = setups.get(userId);
  const rows = [];
  for (let i = 0; i < st.questions.length; i += 5) {
    const row = new ActionRowBuilder();
    for (let j = i; j < Math.min(i + 5, st.questions.length); j++) {
      const q = st.questions[j];
      row.addComponents(new ButtonBuilder()
        .setCustomId(`tog_${userId}_${j}`)
        .setLabel(`Q${j + 1}: ${q.yesno ? 'YES/NO' : 'TEXT'}`)
        .setStyle(q.yesno ? ButtonStyle.Success : ButtonStyle.Secondary));
    }
    rows.push(row);
  }
  rows.push(new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`save_${userId}`).setLabel('✔ SAVE APPLICATION').setStyle(ButtonStyle.Primary)));
  return rows;
}

async function runSetup(interaction) {
  const userId = interaction.user.id;
  const name = interaction.options.getString('name');
  const count = interaction.options.getInteger('questions');
  const questions = [];
  let current = interaction;

  try {
    // Discord modals hold max 5 inputs -> chunk into multiple modals
    for (let start = 0; start < count; start += 5) {
      const end = Math.min(start + 5, count);
      const modal = new ModalBuilder().setCustomId(`setup_${start}`).setTitle(`Questions ${start + 1}-${end} of ${count}`);
      for (let i = start; i < end; i++) {
        modal.addComponents(new ActionRowBuilder().addComponents(
          new TextInputBuilder().setCustomId(`q${i}`).setLabel(`Question ${i + 1}`).setStyle(TextInputStyle.Short).setRequired(true).setMaxLength(200)));
      }
      await current.showModal(modal);
      const submitted = await current.awaitModalSubmit({ filter: i => i.user.id === userId, time: 10 * 60_000 });
      for (let i = start; i < end; i++) questions.push({ text: submitted.fields.getTextInputValue(`q${i}`), yesno: false });
      current = submitted;
    }
  } catch { return; } // wizard abandoned

  setups.set(userId, { name, questions });
  await current.update({
    embeds: [hl2('▓▒░ APPLICATION SETUP ░▒▓',
      `**${name}** — ${questions.length} questions.\n\nClick a question to toggle it between **TEXT** and **YES/NO**, then press **SAVE**.`)],
    components: setupRows(userId),
    fetchReply: true,
  }).catch(() => {});
}

// ---------------- APPLICATION FLOW (DM) ----------------
async function startApplication(user, app) {
  if (sessions.has(user.id)) {
    await user.send('⚠ You already have an application in progress. Finish or cancel it first.').catch(() => {});
    return true;
  }
  let dm;
  try { dm = await user.createDM(); }
  catch { return false; }
  sessions.set(user.id, { appId: app.id, index: 0, answers: [], start: Date.now(), deadline: Date.now() + SESSION_MS, dm });
  await dm.send({
    embeds: [hl2('▓▒░ APPLICATION TERMINAL ░▒▓',
      `**Position:** ${app.name}\n**Questions:** ${app.questions.length}\n**Time limit:** 30 minutes\n\nConfirm below to begin.`)],
    components: [new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId(`appstart_${app.id}`).setLabel('CONFIRM — START').setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId('appcancel').setLabel('CANCEL').setStyle(ButtonStyle.Danger))],
  });
  return true;
}

function expireSession(user) {
  const s = sessions.get(user.id);
  if (!s) return;
  sessions.delete(user.id);
  s.dm.send({ embeds: [hl2('⏱ TIME EXPIRED', 'Your 30 minutes ran out. **Application failed.** Start over from the server panel.')] }).catch(() => {});
}

async function askNext(user) {
  const s = sessions.get(user.id);
  if (!s) return;
  const app = data.applications[s.appId];
  if (!app) { sessions.delete(user.id); return; }
  if (Date.now() > s.deadline) return expireSession(user);
  if (s.index >= app.questions.length) return finishApplication(user);

  const q = app.questions[s.index];
  const emb = hl2(`QUESTION ${s.index + 1}/${app.questions.length}`,
    `${q.text}\n\n⏱ Time remaining: **${fmt(s.deadline - Date.now())}**`);

  if (q.yesno) {
    await s.dm.send({ embeds: [emb], components: [new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('ans_yes').setLabel('YES').setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId('ans_no').setLabel('NO').setStyle(ButtonStyle.Danger))] });
  } else {
    await s.dm.send({ embeds: [emb] });
    try {
      const msgs = await s.dm.awaitMessages({ filter: m => m.author.id === user.id, max: 1, time: s.deadline - Date.now(), errors: ['time'] });
      s.answers.push(msgs.first().content.slice(0, 1000));
      s.index++;
      askNext(user);
    } catch { expireSession(user); }
  }
}

async function finishApplication(user) {
  const s = sessions.get(user.id);
  const app = data.applications[s.appId];
  const elapsed = Date.now() - s.start;
  const subId = Date.now().toString(36);
  data.submissions[subId] = {
    appId: app.id, appName: app.name,
    applicantId: user.id, applicantTag: user.tag,
    questions: app.questions.map(q => q.text), answers: s.answers,
    status: 'pending', decidedBy: null, at: Date.now(),
  };
  saveData();
  sessions.delete(user.id);

  await s.dm.send({ embeds: [hl2('✔ APPLICATION TRANSMITTED',
    `Your application for **${app.name}** has been sent.\n⏱ Completion time: **${fmt(elapsed)}**\n\nThe Combine will respond shortly.`)], components: [] }).catch(() => {});

  const desc = data.submissions[subId].questions.map((q, i) =>
    `**Q${i + 1}.** ${q}\n**A:** ${s.answers[i] ?? '—'}`).join('\n\n');
  const channel = await client.channels.fetch(APPS_CHANNEL_ID);
  await channel.send({
    embeds: [hl2(`NEW APPLICATION — ${app.name}`, `**Applicant:** ${user.tag} (<@${user.id}>)\n**Time:** ${fmt(elapsed)}\n\n${desc}`)],
    components: [new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId(`dec_a_${subId}`).setLabel('✔ ACCEPT').setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId(`dec_r_${subId}`).setLabel('✖ REJECT').setStyle(ButtonStyle.Danger))],
  });
}

// ---------------- INTERACTION ROUTER ----------------
client.on('interactionCreate', async (interaction) => {
  try {
    // ----- slash commands -----
    if (interaction.isChatInputCommand()) {
      if (interaction.guildId !== GUILD_ID) return;
      if (interaction.commandName === 'setup-application') return runSetup(interaction);
      if (interaction.commandName === 'manage-applications') {
        const opts = Object.values(data.applications).map(a => ({
          label: a.name.slice(0, 90), value: a.id,
          description: a.open ? 'OPEN' : 'CLOSED',
          emoji: a.open ? '🟢' : '🔴',
        }));
        if (!opts.length) return interaction.reply({ content: 'No applications exist yet.', ephemeral: true });
        return interaction.reply({ embeds: [hl2('MANAGE APPLICATIONS', 'Pick one to edit.')], components: [
          new ActionRowBuilder().addComponents(new StringSelectMenuBuilder().setCustomId('mgpick').setPlaceholder('Select application…').addOptions(opts))], ephemeral: true });
      }
      if (interaction.commandName === 'send-panel') {
        const list = Object.values(data.applications).map(a => `${a.open ? '🟢' : '🔴'} **${a.name}**`).join('\n') || '*No applications yet.*';
        const msg = await interaction.channel.send({ embeds: [hl2('▓▒░ APPLICATIONS ░▒▓', `${list}\n\nPress the button below to apply.`)], components: [
          new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('apppanel').setLabel('🗂 BROWSE APPLICATIONS').setStyle(ButtonStyle.Primary))] });
        return interaction.reply({ content: 'Panel posted.', ephemeral: true });
      }
    }

    // ----- setup wizard toggles -----
    if (interaction.isButton() && interaction.customId.startsWith('tog_')) {
      const [, uid, idx] = interaction.customId.split('_');
      if (interaction.user.id !== uid) return interaction.reply({ content: 'Not your setup.', ephemeral: true });
      const st = setups.get(uid);
      if (!st) return interaction.reply({ content: 'Setup expired.', ephemeral: true });
      st.questions[+idx].yesno = !st.questions[+idx].yesno;
      return interaction.update({ components: setupRows(uid) });
    }

    if (interaction.isButton() && interaction.customId.startsWith('save_')) {
      const uid = interaction.customId.split('_')[1];
      if (interaction.user.id !== uid) return interaction.reply({ content: 'Not your setup.', ephemeral: true });
      const st = setups.get(uid);
      if (!st) return interaction.reply({ content: 'Setup expired.', ephemeral: true });
      const id = String(Date.now().toString(36));
      data.applications[id] = { id, name: st.name, questions: st.questions, open: true, acceptRoleId: null, createdBy: interaction.user.tag, createdAt: Date.now() };
      saveData();
      setups.delete(uid);
      return interaction.update({ embeds: [hl2('✔ SAVED', `**${st.name}** is now live. Use \`/send-panel\` to post the browser.`)], components: [] });
    }

    // ----- manage panel -----
    if (interaction.isStringSelectMenu() && interaction.customId === 'mgpick') {
      const app = data.applications[interaction.values[0]];
      const row1 = new ActionRowBuilder().addComponents(new ButtonBuilder()
        .setCustomId(`mgtgl_${app.id}`).setLabel(app.open ? '🔴 CLOSE APPLICATION' : '🟢 OPEN APPLICATION').setStyle(app.open ? ButtonStyle.Danger : ButtonStyle.Success));
      const row2 = new ActionRowBuilder().addComponents(new RoleSelectMenuBuilder().setCustomId(`mgrole_${app.id}`).setPlaceholder('Reviewer role (accept/reject)'));
      return interaction.update({ embeds: [hl2(`MANAGE — ${app.name}`,
        `Status: ${app.open ? '🟢 OPEN' : '🔴 CLOSED'}\nReviewer role: ${app.acceptRoleId ? `<@&${app.acceptRoleId}>` : '*not set*'}`)], components: [row1, row2] });
    }

    if (interaction.isButton() && interaction.customId.startsWith('mgtgl_')) {
      const app = data.applications[interaction.customId.split('_')[1]];
      app.open = !app.open;
      saveData();
      const row2 = new ActionRowBuilder().addComponents(new RoleSelectMenuBuilder().setCustomId(`mgrole_${app.id}`).setPlaceholder('Reviewer role (accept/reject)'));
      return interaction.update({ embeds: [hl2(`MANAGE — ${app.name}`,
        `Status: ${app.open ? '🟢 OPEN' : '🔴 CLOSED'}\nReviewer role: ${app.acceptRoleId ? `<@&${app.acceptRoleId}>` : '*not set*'}`)],
        components: [new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`mgtgl_${app.id}`).setLabel(app.open ? '🔴 CLOSE APPLICATION' : '🟢 OPEN APPLICATION').setStyle(app.open ? ButtonStyle.Danger : ButtonStyle.Success)), row2] });
    }

    if (interaction.isRoleSelectMenu() && interaction.customId.startsWith('mgrole_')) {
      const app = data.applications[interaction.customId.split('_')[1]];
      app.acceptRoleId = interaction.values[0];
      saveData();
      return interaction.reply({ content: `✔ Reviewer role set to <@&${app.acceptRoleId}> for **${app.name}**.`, ephemeral: true });
    }

    // ----- applications browser -----
    if (interaction.isButton() && interaction.customId === 'apppanel') {
      const opts = Object.values(data.applications).map(a => ({ label: a.name.slice(0, 90), value: a.id, description: a.open ? 'OPEN' : 'CLOSED', emoji: a.open ? '🟢' : '🔴' }));
      if (!opts.length) return interaction.reply({ content: 'No applications available yet.', ephemeral: true });
      return interaction.reply({ embeds: [hl2('▓▒░ SELECT APPLICATION ░▒▓', '🟢 = open\n🔴 = closed')], components: [
        new ActionRowBuilder().addComponents(new StringSelectMenuBuilder().setCustomId('apppick').setPlaceholder('Choose an application…').addOptions(opts)),
        new ActionRowBuilder().addComponents(new ButtonBuilder().setLabel('📩 JUMP TO DMs').setStyle(ButtonStyle.Link).setURL('https://discord.com/channels/@me'))], ephemeral: true });
    }

    if (interaction.isStringSelectMenu() && interaction.customId === 'apppick') {
      const app = data.applications[interaction.values[0]];
      if (!app) return interaction.reply({ content: 'Application no longer exists.', ephemeral: true });
      if (!app.open) return interaction.reply({ content: `🔴 **${app.name}** is currently **CLOSED**.`, ephemeral: true });
      await interaction.deferUpdate();
      const ok = await startApplication(interaction.user, app);
      return interaction.followUp(ok
        ? { content: '📩 Sent! Continue in your DMs with the bot.', ephemeral: true, components: [new ActionRowBuilder().addComponents(new ButtonBuilder().setLabel('📩 OPEN DMs').setStyle(ButtonStyle.Link).setURL('https://discord.com/channels/@me'))] }
        : { content: '❌ I cannot DM you — enable DMs from server members and try again.', ephemeral: true });
    }

    // ----- DM session -----
    if (interaction.isButton() && interaction.customId.startsWith('appstart_')) {
      const s = sessions.get(interaction.user.id);
      if (!s || s.appId !== interaction.customId.split('_')[1])
        return interaction.reply({ content: '⚠ This session expired — start again from the server panel.', ephemeral: true });
      await interaction.update({ components: [] });
      return askNext(interaction.user);
    }

    if (interaction.isButton() && interaction.customId === 'appcancel') {
      sessions.delete(interaction.user.id);
      return interaction.update({ embeds: [hl2('✖ CANCELLED', 'Application cancelled.')], components: [] });
    }

    if (interaction.isButton() && (interaction.customId === 'ans_yes' || interaction.customId === 'ans_no')) {
      const s = sessions.get(interaction.user.id);
      if (!s) return interaction.reply({ content: '⚠ Session expired.', ephemeral: true });
      if (Date.now() > s.deadline) { await interaction.update({ components: [] }); return expireSession(interaction.user); }
      s.answers.push(interaction.customId === 'ans_yes' ? 'Yes' : 'No');
      s.index++;
      await interaction.update({ components: [] });
      return askNext(interaction.user);
    }

    // ----- accept / reject -----
    if (interaction.isButton() && interaction.customId.startsWith('dec_')) {
      const [, action, subId] = interaction.customId.split('_');
      const sub = data.submissions[subId];
      if (!sub || sub.status !== 'pending') return interaction.reply({ content: 'Already decided.', ephemeral: true });
      const app = data.applications[sub.appId];
      const allowed = interaction.member.permissions.has(PermissionFlagsBits.ManageGuild)
        || (app?.acceptRoleId && interaction.member.roles.cache.has(app.acceptRoleId));
      if (!allowed) return interaction.reply({ content: '❌ You do not have permission to decide this application.', ephemeral: true });

      sub.status = action === 'a' ? 'accepted' : 'rejected';
      sub.decidedBy = interaction.user.tag;
      saveData();

      const applicant = await client.users.fetch(sub.applicantId).catch(() => null);
      if (applicant) {
        await applicant.send({ embeds: [action === 'a'
          ? hl2('✔ APPLICATION ACCEPTED', `Congratulations, citizen.\nYour application for **${sub.appName}** was **ACCEPTED** by **${interaction.user.tag}**.`)
          : hl2('✖ APPLICATION REJECTED', `Your application for **${sub.appName}** was **REJECTED** by **${interaction.user.tag}**.`)] }).catch(() => {});
      }
      const original = EmbedBuilder.from(interaction.message.embeds[0]);
      original.setTitle(`${sub.status === 'accepted' ? '✔ ACCEPTED' : '✖ REJECTED'} — ${sub.appName}`);
      original.setFooter({ text: `Decided by ${interaction.user.tag}` });
      return interaction.update({ embeds: [original], components: [new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`dec_a_${subId}`).setLabel('✔ ACCEPT').setStyle(ButtonStyle.Success).setDisabled(true),
        new ButtonBuilder().setCustomId(`dec_r_${subId}`).setLabel('✖ REJECT').setStyle(ButtonStyle.Danger).setDisabled(true))] });
    }
  } catch (err) { console.error(err); }
});

client.once('ready', async () => {
  console.log(`Logged in as ${client.user.tag}`);
  const rest = new REST().setToken(process.env.DISCORD_TOKEN);
  await rest.put(Routes.applicationGuildCommands(process.env.CLIENT_ID, GUILD_ID), { body: commands.map(c => c.toJSON()) });
  console.log('Slash commands registered.');
});

client.login(process.env.DISCORD_TOKEN);
