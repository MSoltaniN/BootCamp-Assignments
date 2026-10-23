# %% [markdown]
# # بخش ۱۰ — ساخت عامل تقویتیِ کوچک با Q-learning
#
# محیط خودساخته: شبکهٔ ۴×۴، شروع `(0,0)`، هدف `(3,3)`، چاله‌ها `(1,1)` و `(2,3)`.
# اعمال: بالا/پایین/چپ/راست. برخورد با مرز، عامل را در همان خانه نگه می‌دارد.
# پاداش: هر گام عادی −۰٫۰۱، هدف +۱، چاله −۱. هدف و چاله پایان اپیزودند و سقف هر
# اپیزود ۴۰ گام است.

# %%
import json
import os
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

warnings.filterwarnings('ignore')
SEED = 42
OUT = 'out'
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## ۱۰.۱ پیاده‌سازی محیط: `reset` و `step`

# %%
class GridWorld:
    """شبکهٔ ۴×۴؛ حالت = (row, col) و عمل = ۰..۳."""

    N = 4
    START = (0, 0)
    GOAL = (3, 3)
    HOLES = {(1, 1), (2, 3)}
    ACTIONS = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1)}   # up, down, left, right
    ACTION_NAMES = {0: 'up', 1: 'down', 2: 'left', 3: 'right'}
    STEP_REWARD = -0.01
    GOAL_REWARD = 1.0
    HOLE_REWARD = -1.0
    MAX_STEPS = 40

    def __init__(self, max_steps=MAX_STEPS):
        self.max_steps = max_steps
        self.reset()

    def reset(self):
        self.pos = self.START
        self.t = 0
        self.done = False
        return self.pos

    def step(self, action):
        """یک گام؛ خروجی: (state بعدی، پاداش، پایان، اطلاعات)"""
        assert action in self.ACTIONS, f'invalid action {action}'
        self.t += 1
        dr, dc = self.ACTIONS[action]
        nr, nc = self.pos[0] + dr, self.pos[1] + dc

        # برخورد با مرز: ماندن در همان خانه
        hit_wall = not (0 <= nr < self.N and 0 <= nc < self.N)
        if hit_wall:
            nr, nc = self.pos
        self.pos = (nr, nc)

        if self.pos == self.GOAL:
            return self.pos, self.GOAL_REWARD, True, {'outcome': 'goal', 'steps': self.t,
                                                      'hit_wall': hit_wall}
        if self.pos in self.HOLES:
            return self.pos, self.HOLE_REWARD, True, {'outcome': 'hole', 'steps': self.t,
                                                      'hit_wall': hit_wall}
        if self.t >= self.max_steps:
            return self.pos, self.STEP_REWARD, True, {'outcome': 'timeout', 'steps': self.t,
                                                      'hit_wall': hit_wall}
        return self.pos, self.STEP_REWARD, False, {'outcome': 'step', 'steps': self.t,
                                                   'hit_wall': hit_wall}

    # ---- توابع کمکی برای کدگذاری حالت ----
    @classmethod
    def state_index(cls, pos):
        return pos[0] * cls.N + pos[1]

    @classmethod
    def index_state(cls, idx):
        return (idx // cls.N, idx % cls.N)

    @classmethod
    def is_terminal(cls, pos):
        return pos == cls.GOAL or pos in cls.HOLES


env = GridWorld()
N_STATES = env.N * env.N
N_ACTIONS = len(env.ACTIONS)
print('states:', N_STATES, '| actions:', N_ACTIONS)
print('start:', env.START, '| goal:', env.GOAL, '| holes:', env.HOLES)

# %% [markdown]
# ### آزمون‌های کوچک: مرز، چاله، هدف و سقف گام

# %%
tests = []

# ۱) حرکت از مرز: از (0,0) به بالا و چپ → ماندن در (0,0)
for a in [0, 2]:
    env.reset()
    s, r, d, info = env.step(a)
    tests.append({'test': f'move {GridWorld.ACTION_NAMES[a]} from (0,0)',
                  'state': s, 'reward': r, 'done': d, 'outcome': info['outcome']})

# ۲) رسیدن به هدف: مسیر (0,0)->(1,0)->(2,0)->(2,1)->(2,2)->(3,2)->(3,3)
path = [1, 1, 3, 3, 1, 3]
env.reset()
for a in path:
    s, r, d, info = env.step(a)
tests.append({'test': 'reach goal via ' + str(path), 'state': s,
              'reward': r, 'done': d, 'outcome': info['outcome'], 'steps': info['steps']})

# ۳) افتادن در چاله: (0,0)->(1,0)->(1,1)
env.reset()
env.step(1)
s, r, d, info = env.step(3)
tests.append({'test': 'fall into hole (1,1)', 'state': s,
              'reward': r, 'done': d, 'outcome': info['outcome'], 'steps': info['steps']})

# ۴) سقف گام: چرخیدن بین دو خانه برای ۴۰ گام
env = GridWorld(max_steps=5)
env.reset()
outs = [env.step(3 if i % 2 == 0 else 2) for i in range(5)]
s, r, d, info = outs[-1]
tests.append({'test': 'timeout after 5 dummy steps', 'state': s,
              'reward': r, 'done': d, 'outcome': info['outcome'], 'steps': info['steps']})

for t in tests:
    print(t)

# %% [markdown]
# ## ۱۰.۲ Q-learning جدولی
#
# $$Q(s,a) \leftarrow Q(s,a) + \alpha\big[r + \gamma \max_{a'} Q(s',a') - Q(s,a)\big]$$
#
# برای حالت پایانی، مقدار هدف فقط `r` است (بدون بوت‌استرپ). سیاست ε-greedy با کاهش
# خطی ε از ۱٫۰ تا ۰٫۰۵ در ۸۰٪ نخست آموزش و سپس ثابت روی ۰٫۰۵.

# %%
ALPHA = 0.1
GAMMA = 0.95
N_EPISODES = 2000
EPS_START, EPS_END = 1.0, 0.05
EPS_DECAY_FRACTION = 0.8


def epsilon_at(ep):
    decay_eps = EPS_DECAY_FRACTION * N_EPISODES
    if ep >= decay_eps:
        return EPS_END
    return EPS_START + (EPS_END - EPS_START) * (ep / decay_eps)


def train_q_learning(n_episodes=N_EPISODES, alpha=ALPHA, gamma=GAMMA, seed=SEED):
    rng = np.random.RandomState(seed)
    Q = np.zeros((N_STATES, N_ACTIONS))
    hist = {'episode': [], 'reward': [], 'success': [], 'steps': [], 'epsilon': []}
    for ep in range(n_episodes):
        env = GridWorld()
        s = GridWorld.state_index(env.reset())
        eps = epsilon_at(ep)
        total, ok = 0.0, False
        while True:
            if rng.rand() < eps:
                a = rng.randint(N_ACTIONS)
            else:
                a = int(np.argmax(Q[s]))
            pos, r, done, info = env.step(a)
            s2 = GridWorld.state_index(pos)
            total += r
            if done:
                Q[s, a] += alpha * (r - Q[s, a])
                ok = (info['outcome'] == 'goal')
                break
            Q[s, a] += alpha * (r + gamma * Q[s2].max() - Q[s, a])
            s = s2
        hist['episode'].append(ep + 1)
        hist['reward'].append(total)
        hist['success'].append(int(ok))
        hist['steps'].append(info['steps'])
        hist['epsilon'].append(eps)
    return Q, hist


Q, hist = train_q_learning()
print(f'trained {N_EPISODES} episodes | alpha={ALPHA} gamma={GAMMA} '
      f'eps {EPS_START}->{EPS_END} | final eps={epsilon_at(N_EPISODES - 1):.3f}')
print('last 100 episodes: mean reward %.3f | success %.0f%%'
      % (np.mean(hist['reward'][-100:]), 100 * np.mean(hist['success'][-100:])))

# %% [markdown]
# ## ۱۰.۳ ارزیابی: سیاست آموخته‌شده در برابر عامل تصادفی
#
# ۲۰۰ اپیزود **بدون اکتشاف** (فقط argmax) برای سیاست، و ۲۰۰ اپیزود با عمل یکنواخت
# تصادفی برای عامل تصادفی. هر دو با بذر ثابت.

# %%
def run_greedy(Q, n_episodes=200):
    rewards, successes, steps = [], [], []
    for _ in range(n_episodes):
        env = GridWorld()
        s = GridWorld.state_index(env.reset())
        total, ok = 0.0, False
        while True:
            a = int(np.argmax(Q[s]))
            pos, r, done, info = env.step(a)
            total += r
            if done:
                ok = (info['outcome'] == 'goal')
                break
            s = GridWorld.state_index(pos)
        rewards.append(total)
        successes.append(int(ok))
        steps.append(info['steps'])
    return np.array(rewards), np.array(successes), np.array(steps)


def run_random(n_episodes=200, seed=7):
    rng = np.random.RandomState(seed)
    rewards, successes, steps = [], [], []
    for _ in range(n_episodes):
        env = GridWorld()
        env.reset()
        total, ok = 0.0, False
        while True:
            _, r, done, info = env.step(rng.randint(N_ACTIONS))
            total += r
            if done:
                ok = (info['outcome'] == 'goal')
                break
        rewards.append(total)
        successes.append(int(ok))
        steps.append(info['steps'])
    return np.array(rewards), np.array(successes), np.array(steps)


g_rew, g_succ, g_steps = run_greedy(Q)
r_rew, r_succ, r_steps = run_random()
print(f'learned policy : mean reward={g_rew.mean():.4f} success={100 * g_succ.mean():.1f}% '
      f'mean steps={g_steps.mean():.1f}')
print(f'random policy  : mean reward={r_rew.mean():.4f} success={100 * r_succ.mean():.1f}% '
      f'mean steps={r_steps.mean():.1f}')
print(f'theoretical optimal return = 1 - 0.01*5 = 0.95 (path length 6)')

# %% [markdown]
# ## سیاست نهایی و منحنی یادگیری

# %%
fig, ax = plt.subplots(figsize=(5.6, 5.6))
arrow_dirs = {0: (0, 1), 1: (0, -1), 2: (-1, 0), 3: (1, 0)}  # up/down/left/right در مختصات نمودار
# سطر ۰ بالای نمودار است، پس «بالا» = +y
for r in range(4):
    for c in range(4):
        cell = (r, c)
        if cell == GridWorld.GOAL:
            color = '#2e7d32'
        elif cell in GridWorld.HOLES:
            color = '#8e2f2f'
        elif cell == GridWorld.START:
            color = '#3b6ea5'
        else:
            color = '#f2f2f2'
        ax.add_patch(Rectangle((c, 3 - r), 1, 1, facecolor=color, edgecolor='k', lw=1.2))
        if cell == GridWorld.GOAL or cell in GridWorld.HOLES or cell == GridWorld.START:
            label = 'GOAL' if cell == GridWorld.GOAL else ('HOLE' if cell in GridWorld.HOLES else 'START')
            ax.text(c + .5, 3 - r + .5, label, ha='center', va='center',
                    color='white', fontsize=9, weight='bold')
            continue
        q_row = Q[GridWorld.state_index(cell)]
        if np.allclose(q_row, 0.0):
            ax.text(c + .5, 3 - r + .5, '?', ha='center', va='center',
                    color='#888', fontsize=15, weight='bold')
            continue
        a = int(np.argmax(q_row))
        dx, dy = arrow_dirs[a]
        ax.add_patch(FancyArrowPatch((c + .5 - 0.28 * dx, 3 - r + .5 - 0.28 * dy),
                                     (c + .5 + 0.28 * dx, 3 - r + .5 + 0.28 * dy),
                                     arrowstyle='-|>', mutation_scale=16, lw=2,
                                     color='#1f3b57'))
ax.set_xlim(0, 4); ax.set_ylim(0, 4)
ax.set_xticks([]); ax.set_yticks([])
ax.set_title('Learned greedy policy (arrows = argmax Q)')
ax.set_aspect('equal')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec10_policy.png'), dpi=130)
plt.close()

# %%
fig, ax = plt.subplots(figsize=(8, 4.4))
roll = 50
rew = np.array(hist['reward'], dtype=float)
succ = np.array(hist['success'], dtype=float)
eps_axis = np.array(hist['episode'])[roll - 1:]
ax.plot(eps_axis, np.convolve(rew, np.ones(roll) / roll, mode='valid'),
        color='#3b6ea5', label=f'reward (rolling {roll})')
ax2 = ax.twinx()
ax2.plot(eps_axis, np.convolve(succ, np.ones(roll) / roll, mode='valid'),
         color='#2e7d32', alpha=.8, label=f'success rate (rolling {roll})')
ax2.set_ylabel('success rate (rolling mean)', color='#2e7d32')
ax2.set_ylim(-0.02, 1.02)
ax.set(xlabel='episode', ylabel='episode return')
ax.set_title('Q-learning learning curve')
ax.grid(alpha=.3)
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='lower right')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec10_learning_curve.png'), dpi=130)
plt.close()

# %%
fig, ax = plt.subplots(figsize=(5.4, 4.6))
vmax = float(np.abs(Q).max())
im = ax.imshow(Q.max(axis=1).reshape(4, 4), cmap='RdYlGn', vmin=-vmax, vmax=vmax)
for r in range(4):
    for c in range(4):
        ax.text(c, r, f'{Q.max(axis=1).reshape(4, 4)[r, c]:.2f}', ha='center', va='center', fontsize=8)
ax.set_xticks(range(4)); ax.set_yticks(range(4))
ax.set_title('max_a Q(s,a) per cell')
plt.colorbar(im, ax=ax, fraction=.046)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec10_qvalues.png'), dpi=130)
plt.close()
print('figures ->', OUT)

# %%
policy = {}
for r in range(4):
    for c in range(4):
        cell = (r, c)
        if cell in GridWorld.HOLES or cell == GridWorld.GOAL:
            continue
        a = int(np.argmax(Q[GridWorld.state_index(cell)]))
        policy[str(cell)] = GridWorld.ACTION_NAMES[a]
untrained = [GridWorld.index_state(i) for i in range(N_STATES)
             if not GridWorld.is_terminal(GridWorld.index_state(i))
             and np.allclose(Q[i], 0.0)]
print('states with Q == 0 (never visited):', untrained)
print('greedy actions:', json.dumps(policy, indent=0))

results = {
    'n_states': N_STATES,
    'n_actions': N_ACTIONS,
    'start': list(GridWorld.START),
    'goal': list(GridWorld.GOAL),
    'holes': [list(h) for h in GridWorld.HOLES],
    'rewards': {'step': GridWorld.STEP_REWARD, 'goal': GridWorld.GOAL_REWARD,
                'hole': GridWorld.HOLE_REWARD},
    'max_steps': GridWorld.MAX_STEPS,
    'tests': tests,
    'training': {'episodes': N_EPISODES, 'alpha': ALPHA, 'gamma': GAMMA,
                 'eps_start': EPS_START, 'eps_end': EPS_END,
                 'eps_decay_fraction': EPS_DECAY_FRACTION},
    'last100_train': {'mean_reward': round(float(np.mean(rew[-100:])), 4),
                      'success_rate': round(float(np.mean(succ[-100:])), 4)},
    'learned_policy': {'mean_reward': round(float(g_rew.mean()), 4),
                       'success_rate': round(float(g_succ.mean()), 4),
                       'mean_steps': round(float(g_steps.mean()), 2)},
    'random_policy': {'mean_reward': round(float(r_rew.mean()), 4),
                      'success_rate': round(float(r_succ.mean()), 4),
                      'mean_steps': round(float(r_steps.mean()), 2)},
    'policy_grid': policy,
    'untrained_states': [list(s) for s in untrained],
}
with open(os.path.join(OUT, 'sec10_results.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('saved out/sec10_results.json')
