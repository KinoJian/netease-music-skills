#!/usr/bin/env node

/**
 * netease-music-skills installer
 * Copies music-curator skill to ~/.claude/skills/
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SKILLS = ['music-curator'];

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
  console.log('🎵 netease-music-skills — 网易云音乐标签管理 Claude Code 技能');
  console.log('');

  // Step 0: install ncm-cli
  console.log('━━━ 前置依赖 ━━━');
  console.log('1️⃣  安装 ncm-cli（网易云音乐命令行工具）');
  console.log('   npm install -g @music163/ncm-cli');
  console.log('');
  try {
    const version = execSync('ncm-cli --version', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] }).trim();
    console.log('   ✅ 已安装: ' + version);
  } catch (e) {
    console.log('   ⚠️ 未安装，请运行: npm install -g @music163/ncm-cli');
  }
  console.log('');

  // Step 1: install music-curator
  console.log('━━━ 安装自研技能 ━━━');
  let totalFiles = 0;
  for (const skill of SKILLS) {
    const src = path.join(pkgDir, 'skills', skill);
    const dest = path.join(skillsDir, skill);

    if (!fs.existsSync(src)) {
      console.log('⚠ 跳过 ' + skill + ': 源目录不存在');
      continue;
    }

    const fileCount = copyDir(src, dest);
    console.log('✅ ' + skill + ' → ' + dest + ' (' + fileCount + ' files)');
    totalFiles += fileCount;
  }

  // Step 2: tools location
  const toolsDir = path.join(pkgDir, 'tools');
  if (fs.existsSync(toolsDir)) {
    console.log('');
    console.log('📦 标签管理工具位置:');
    console.log('   ' + toolsDir);
    console.log('   使用前: export NCM_LIKED_PLAYLIST_ID="你的红心歌单ID"');
  }

  // Step 3: official skills hint
  console.log('');
  console.log('━━━ 安装网易官方技能（推荐） ━━━');
  console.log('npx skills add https://github.com/NetEase/skills');
  console.log('（包含 ncm-cli-setup、netease-music-cli、netease-music-assistant）');
  console.log('');

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('✅ 安装完成！在 Claude Code 中使用 /music-curator');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('');
}

main();
