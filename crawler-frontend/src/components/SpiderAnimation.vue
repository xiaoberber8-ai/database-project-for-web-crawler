<template>
  <div class="spider-scene" :class="{ sleeping }">
    <div class="ground"></div>
    <div class="cloud cloud-1"></div>
    <div class="cloud cloud-2"></div>

    <!-- 数据库 -->
    <div class="database">
      <div class="db-top"></div>
      <div class="db-body">
        <div class="db-ellipse db-ellipse-1"></div>
        <div class="db-ellipse db-ellipse-2"></div>
        <div class="db-ellipse db-ellipse-3"></div>
      </div>
      <div class="db-base"></div>
      <div class="db-glow"></div>
    </div>

    <!-- 数据包（小方块）飞向数据库（运行中才显示） -->
    <template v-if="!sleeping">
      <div class="data-packet packet-1"></div>
      <div class="data-packet packet-2"></div>
      <div class="data-packet packet-3"></div>
    </template>

    <!-- 蜘蛛 -->
    <div class="spider">
      <!-- 身体 -->
      <div class="spider-body"></div>

      <!-- 眼睛：运行中是圆眼，睡觉时是闭眼（一条线） -->
      <div class="spider-eye eye-left" :class="{ 'eye-closed': sleeping }"></div>
      <div class="spider-eye eye-right" :class="{ 'eye-closed': sleeping }"></div>

      <!-- 嘴：运行中微笑，睡觉时小 o 形 -->
      <div class="spider-smile" :class="{ 'sleep-mouth': sleeping }"></div>

      <!-- 腿 -->
      <div class="leg leg-1"></div>
      <div class="leg leg-2"></div>
      <div class="leg leg-3"></div>
      <div class="leg leg-4"></div>
      <div class="leg leg-5"></div>
      <div class="leg leg-6"></div>
      <div class="leg leg-7"></div>
      <div class="leg leg-8"></div>

      <!-- 背着的数据（运行中，去程显示、回程隐藏） -->
      <div v-if="!sleeping" class="carry-data">
        <span class="data-binary">data</span>
      </div>

      <!-- 睡觉气泡 Zzz（睡觉时显示） -->
      <div v-if="sleeping" class="sleep-zzz">
        <span class="z z-1">z</span>
        <span class="z z-2">z</span>
        <span class="z z-3">z</span>
      </div>

      <!-- 蛛丝 -->
      <div class="silk"></div>
    </div>

    <!-- 进度提示 -->
    <div class="scene-label">
      <span class="dot" :class="{ 'dot-resting': sleeping }"></span>
      {{ sleeping ? '小蜘蛛正在休息...' : '小蜘蛛正在搬运数据到数据库...' }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  sleeping: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.spider-scene {
  position: relative;
  width: 100%;
  height: 220px;
  background: linear-gradient(180deg, #f5f7fa 0%, #eef2f7 100%);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

/* 地面 */
.ground {
  position: absolute;
  bottom: 28px;
  left: 0;
  right: 0;
  height: 4px;
  background: repeating-linear-gradient(
    90deg,
    #5a5a5a 0,
    #5a5a5a 8px,
    transparent 8px,
    transparent 12px
  );
  z-index: 1;
}
.ground::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -4px;
  height: 4px;
  background: repeating-linear-gradient(
    90deg,
    #999 0,
    #999 4px,
    transparent 4px,
    transparent 8px
  );
  opacity: 0.5;
}

/* 云朵 */
.cloud {
  position: absolute;
  width: 40px;
  height: 14px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow:
    14px 2px 0 0 #ffffff,
    -14px 4px 0 -2px #ffffff;
  opacity: 0.9;
  z-index: 0;
}
.cloud-1 {
  top: 22px;
  left: 12%;
  animation: cloud-move 18s linear infinite;
}
.cloud-2 {
  top: 50px;
  left: 60%;
  animation: cloud-move 24s linear infinite reverse;
  opacity: 0.7;
}
@keyframes cloud-move {
  0%   { transform: translateX(0); }
  100% { transform: translateX(360px); }
}

/* 数据库（圆柱） */
.database {
  position: absolute;
  right: 36px;
  bottom: 32px;
  width: 64px;
  height: 90px;
  z-index: 2;
}
.db-top {
  position: absolute;
  top: 0;
  left: 0;
  width: 64px;
  height: 14px;
  background: #5a8fcf;
  border-radius: 50% / 50%;
  border: 2px solid #2c4d6e;
  z-index: 3;
}
.db-body {
  position: absolute;
  top: 7px;
  left: 0;
  width: 64px;
  height: 76px;
  background: linear-gradient(90deg, #6ba3d8 0%, #4a7eb3 50%, #6ba3d8 100%);
  border-left: 2px solid #2c4d6e;
  border-right: 2px solid #2c4d6e;
  overflow: hidden;
}
.db-ellipse {
  position: absolute;
  left: -2px;
  width: 64px;
  height: 14px;
  background: #4a7eb3;
  border-radius: 50% / 50%;
  border: 2px solid #2c4d6e;
  border-bottom: none;
}
.db-ellipse-1 { top: 14px; }
.db-ellipse-2 { top: 36px; }
.db-ellipse-3 { top: 58px; }
.db-base {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 64px;
  height: 14px;
  background: #5a8fcf;
  border-radius: 50% / 50%;
  border: 2px solid #2c4d6e;
  border-top: none;
  z-index: 3;
}
.db-glow {
  position: absolute;
  inset: -6px;
  background: radial-gradient(circle, rgba(103, 194, 58, 0.4) 0%, transparent 70%);
  border-radius: 50%;
  opacity: 0;
  animation: db-glow 2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes db-glow {
  0%, 100% { opacity: 0; }
  50%      { opacity: 1; }
}

/* 数据包飞向数据库 */
.data-packet {
  position: absolute;
  width: 10px;
  height: 10px;
  background: #fbbf24;
  border: 2px solid #92400e;
  border-radius: 2px;
  z-index: 4;
  opacity: 0;
}
.packet-1 {
  bottom: 110px;
  right: 110px;
  animation: packet-fly 1.6s ease-in infinite;
  animation-delay: 0s;
}
.packet-2 {
  bottom: 110px;
  right: 110px;
  animation: packet-fly 1.6s ease-in infinite;
  animation-delay: 0.5s;
}
.packet-3 {
  bottom: 110px;
  right: 110px;
  animation: packet-fly 1.6s ease-in infinite;
  animation-delay: 1s;
}
@keyframes packet-fly {
  0% {
    transform: translate(0, 0);
    opacity: 0;
  }
  20% { opacity: 1; }
  100% {
    transform: translate(70px, -50px);
    opacity: 0;
  }
}

/* 蜘蛛 */
.spider {
  position: absolute;
  left: 30px;
  bottom: 32px;
  width: 60px;
  height: 60px;
  z-index: 5;
  /* spider-walk 控制 left（到达数据库旁），spider-bounce 控制上下起伏 */
  animation: spider-walk 2.6s ease-in-out infinite alternate,
             spider-bounce 0.24s ease-in-out infinite alternate;
}
@keyframes spider-walk {
  /* 起点 left:30px，终点贴近数据库左侧（数据库 right:36px + width:64px = 距右100px，再减 spider 宽 60px + 间距 10px） */
  0%   { left: 30px; }
  100% { left: calc(100% - 170px); }
}
@keyframes spider-bounce {
  0%   { transform: translateY(0); }
  100% { transform: translateY(-4px); }
}

/* 蛛丝 */
.silk {
  position: absolute;
  top: -28px;
  left: 28px;
  width: 1px;
  height: 28px;
  background: rgba(120, 120, 120, 0.6);
  animation: silk-sway 0.8s ease-in-out infinite;
  transform-origin: top center;
}
@keyframes silk-sway {
  0%, 100% { transform: rotate(-3deg); }
  50%      { transform: rotate(3deg); }
}

/* 蜘蛛身体 */
.spider-body {
  position: absolute;
  left: 14px;
  top: 20px;
  width: 32px;
  height: 22px;
  background: #2c2c2c;
  border-radius: 50% 50% 45% 45% / 60% 60% 40% 40%;
  border: 2px solid #1a1a1a;
  box-shadow: inset -3px -3px 0 rgba(255,255,255,0.1);
}

/* 蜘蛛眼睛 */
.spider-eye {
  position: absolute;
  top: 24px;
  width: 6px;
  height: 6px;
  background: #ffffff;
  border-radius: 50%;
  border: 1px solid #1a1a1a;
}
.eye-left  { left: 22px; }
.eye-right { left: 32px; }
.spider-eye::after {
  content: '';
  position: absolute;
  top: 1px;
  left: 1px;
  width: 3px;
  height: 3px;
  background: #1a1a1a;
  border-radius: 50%;
}

/* 蜘蛛微笑 */
.spider-smile {
  position: absolute;
  top: 31px;
  left: 26px;
  width: 8px;
  height: 4px;
  border-bottom: 1.5px solid #1a1a1a;
  border-radius: 0 0 8px 8px;
}

/* 蜘蛛腿 */
.leg {
  position: absolute;
  width: 14px;
  height: 2px;
  background: #1a1a1a;
  border-radius: 1px;
  transform-origin: left center;
}
.leg-1 { top: 24px; left: 8px;  transform: rotate(35deg);  animation: leg-swing-1 0.2s ease-in-out infinite alternate; }
.leg-2 { top: 24px; left: 8px;  transform: rotate(60deg);  animation: leg-swing-2 0.2s ease-in-out infinite alternate; }
.leg-3 { top: 32px; left: 8px;  transform: rotate(85deg);  animation: leg-swing-3 0.2s ease-in-out infinite alternate; }
.leg-4 { top: 38px; left: 8px;  transform: rotate(110deg); animation: leg-swing-4 0.2s ease-in-out infinite alternate; }
.leg-5 { top: 24px; left: 38px; transform: rotate(145deg); animation: leg-swing-1 0.2s ease-in-out infinite alternate; }
.leg-6 { top: 24px; left: 38px; transform: rotate(120deg); animation: leg-swing-2 0.2s ease-in-out infinite alternate; }
.leg-7 { top: 32px; left: 38px; transform: rotate(95deg);  animation: leg-swing-3 0.2s ease-in-out infinite alternate; }
.leg-8 { top: 38px; left: 38px; transform: rotate(70deg);  animation: leg-swing-4 0.2s ease-in-out infinite alternate; }

@keyframes leg-swing-1 {
  0%   { transform: rotate(35deg)  translateY(0); }
  100% { transform: rotate(20deg)  translateY(-2px); }
}
@keyframes leg-swing-2 {
  0%   { transform: rotate(60deg)  translateY(0); }
  100% { transform: rotate(75deg)  translateY(-2px); }
}
@keyframes leg-swing-3 {
  0%   { transform: rotate(85deg)  translateY(0); }
  100% { transform: rotate(100deg) translateY(-1px); }
}
@keyframes leg-swing-4 {
  0%   { transform: rotate(110deg) translateY(0); }
  100% { transform: rotate(125deg) translateY(-1px); }
}

/* 背着的数据 */
.carry-data {
  position: absolute;
  top: -4px;
  left: 16px;
  width: 28px;
  height: 18px;
  background: #fbbf24;
  border: 2px solid #92400e;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  color: #92400e;
  /* carry-visibility: 5.2s 周期，去程可见、回程隐藏（与 spider-walk 2.6s alternate 对应） */
  /* carry-bob: 颠动效果 */
  animation: carry-visibility 5.2s ease-in-out infinite,
             carry-bob 0.24s ease-in-out infinite alternate;
}
@keyframes carry-visibility {
  0%   { opacity: 1; }
  48%  { opacity: 1; }  /* 即将到达数据库，准备放下数据 */
  50%  { opacity: 0; }  /* 到达数据库，数据已入库 */
  98%  { opacity: 0; }  /* 回程空手 */
  100% { opacity: 1; }  /* 回到起点，重新背上数据 */
}
@keyframes carry-bob {
  0%   { transform: translateY(0) rotate(-3deg); }
  100% { transform: translateY(-2px) rotate(3deg); }
}
.data-binary {
  display: inline-block;
}

/* 底部提示 */
.scene-label {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.85);
  padding: 2px 10px;
  border-radius: 10px;
  z-index: 10;
}
.scene-label .dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
  animation: dot-pulse 1s ease-in-out infinite;
}
.scene-label .dot-resting {
  background: #909399;
  animation: none;
}
@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.5; transform: scale(1.2); }
}

/* ============ 睡觉状态 ============ */

/* 睡觉时：停止行走动画，轻微呼吸 */
.spider-scene.sleeping .spider {
  animation: spider-breathe 3s ease-in-out infinite;
  left: 80px; /* 居中一点，挨着数据库旁休息 */
}
@keyframes spider-breathe {
  0%, 100% { transform: translateY(0) scale(1); }
  50%      { transform: translateY(-1px) scale(1.02); }
}

/* 睡觉时：腿不再摆动，自然垂下静止 */
.spider-scene.sleeping .leg {
  animation: none !important;
}

/* 睡觉时：蛛丝也不再摇晃 */
.spider-scene.sleeping .silk {
  animation: none;
}

/* 睡觉时：数据库光晕关闭（没有数据入库） */
.spider-scene.sleeping .db-glow {
  animation: none;
  opacity: 0;
}

/* 闭眼：把圆眼睛变成一条横线 */
.spider-eye.eye-closed {
  height: 2px;
  top: 27px;
  border-radius: 1px;
  background: #1a1a1a;
}
.spider-eye.eye-closed::after {
  display: none;
}

/* 睡觉时的嘴：小 o 形（打呼噜） */
.spider-smile.sleep-mouth {
  width: 4px;
  height: 4px;
  top: 32px;
  left: 28px;
  border: 1.5px solid #1a1a1a;
  border-bottom: none;
  border-radius: 50% 50% 0 0;
  animation: snore 3s ease-in-out infinite;
}
@keyframes snore {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.3); }
}

/* Zzz 睡觉气泡 */
.sleep-zzz {
  position: absolute;
  top: -14px;
  left: 36px;
  z-index: 6;
  pointer-events: none;
}
.sleep-zzz .z {
  position: absolute;
  font-family: 'Comic Sans MS', 'Microsoft YaHei', sans-serif;
  font-weight: bold;
  color: #909399;
  opacity: 0;
}
.sleep-zzz .z-1 {
  font-size: 10px;
  top: 0;
  left: 0;
  animation: zzz-float 3s ease-in-out infinite;
  animation-delay: 0s;
}
.sleep-zzz .z-2 {
  font-size: 12px;
  top: -6px;
  left: 8px;
  animation: zzz-float 3s ease-in-out infinite;
  animation-delay: 1s;
}
.sleep-zzz .z-3 {
  font-size: 14px;
  top: -12px;
  left: 16px;
  animation: zzz-float 3s ease-in-out infinite;
  animation-delay: 2s;
}
@keyframes zzz-float {
  0% {
    opacity: 0;
    transform: translateY(0) translateX(0) scale(0.6);
  }
  20% { opacity: 0.9; }
  100% {
    opacity: 0;
    transform: translateY(-18px) translateX(8px) scale(1.2);
  }
}
</style>
