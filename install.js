#!/usr/bin/env node

/**
 * netease-music-skills installer
 * Copies ncm-cli-setup and music-curator skills to ~/.claude/skills/
 */

const fs = require('fs');
const path = require('path');

const SKILLS = ['ncm-cli-setup', 'music-curator'];

function getClaudeSkillsDir() {
  const home = process.env.HOME || process.env.USERPROFILE;
  if (!home) {
    console.error('ERROR: Cannot determine home directory.');
    process.exit(1);
  }
  return path.join(home, '.claude', 'skills');
}

function copyDir(src, dest) {
  if (!fs.existsSync(src)) return 0;
  fs.mkdirSync(dest, { recursive: true });

  let count = 0;
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      count += copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
      count++;
    }
  }
  return count;
}

function main() {
  const skillsDir = getClaudeSkillsDir();
  const pkgDir = path.resolve(__dirname);

  console.log('');
  console.log('🎵 netease-music-skills — 网易云音乐 Claude Code 技能包');
  console.log('');

  let totalFiles = 0;
  for (const skill of SKILLS) {
    const src = path.join(pkgDir, 'skills', skill);
    const dest = path.join(skillsDir, skill);

    if (!fs.existsSync(src)) {
      console.log(`⚠ 跳过 ${skill}: 源目录不存在`);
      continue;
    }

    const fileCount = copyDir(src, dest);
    console.log(`✅ ${skill} → ${dest} (${fileCount} files)`);
    totalFiles += fileCount;
  }

  // Show tools hint
  const toolsDir = path.join(pkgDir, 'tools');
  if (fs.existsSync(toolsDir)) {
    console.log('');
    console.log('📦 标签管理工具位置:');
    console.log(`   ${toolsDir}`);
    console.log('   使用前请先: export NCM_LIKED_PLAYLIST_ID="你的红心歌单ID"');
  }

  console.log('');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('安装完成！现在在 Claude Code 中:');
  console.log('  /ncm-cli-setup     → 一键安装 ncm-cli + mpv');
  console.log('  /music-curator     → 标签搜索 + 同步红心歌单');
  console.log('');
  console.log('💡 可选：安装网易官方技能');
  console.log('  npx skills add https://github.com/NetEase/skills');
  console.log('  (获取 netease-music-assistant 和 netease-music-cli)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
}

main();
