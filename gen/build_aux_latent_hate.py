#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds an EN auxiliary training dataset from the Latent Hatred implicit-hate corpus
(ElSherief et al., EMNLP 2021; CC BY 4.0) mapped into the StereoQueerEval 7-column schema.

Mapping:
  implicit_hate  -> hate_speech = 'yes_implicit'
  explicit_hate  -> hate_speech = 'yes_explicit'
  not_hate       -> hate_speech = 'no'
  stereotype     -> 'no'   (not annotated in the source)
  target         -> 'none' (Not annotated; Latent targets are non-LGBTQ groups)

Purpose: Task-B (hate_speech) register warm-up ONLY. Never train the target or
stereotype heads on this data.

Usage:
  python gen/build_aux_latent_hate.py
"""

import argparse
import csv
import os
import re

HDR = [
    'StereoQueerEval_id',
    'yt_title',
    'yt_description',
    'yt_comment',
    'stereotype',
    'hate_speech',
    'target'
]

LABEL_MAP = {
    'implicit_hate': 'yes_implicit',
    'explicit_hate': 'yes_explicit',
    'not_hate': 'no'
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-dir', default='implicit-hate-corpus',
                        help='Directory containing the Latent Hatred files')
    parser.add_argument('--out', default='LGBT/AuxImplicitHate_EN_training.tsv',
                        help='Output 7-column TSV path')
    parser.add_argument('--max-not-hate', type=int, default=None,
                        help='Optionally cap how many not_hate rows to keep (None = keep all)')
    args = parser.parse_args()

    stg1_path = os.path.join(args.corpus_dir, 'implicit_hate_v1_stg1.tsv')
    posts_path = os.path.join(args.corpus_dir, 'implicit_hate_v1_stg1_posts.tsv')

    def load(path):
        with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
            return list(csv.DictReader(f, delimiter='\t'))

    stg1 = load(stg1_path)
    posts = load(posts_path)
    assert len(stg1) == len(posts), f'Length mismatch {len(stg1)} vs {len(posts)}'
    align_ok = sum(1 for a, b in zip(stg1, posts) if a['class'] == b['class'])
    assert align_ok == len(stg1), f'Positional alignment failed: {align_ok}/{len(stg1)}'

    not_hate_kept = 0
    rows_out = 0
    label_counts = {}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', newline='') as f:
        f.write('\t'.join(HDR) + '\n')
        for ann, post in zip(stg1, posts):
            src_class = ann['class']
            if src_class == 'not_hate':
                if args.max_not_hate is not None and not_hate_kept >= args.max_not_hate:
                    continue
                not_hate_kept += 1

            text = re.sub(r'[\t\r\n]+', ' ', (post['post'] or '').strip())
            if not text:
                continue

            hate_label = LABEL_MAP[src_class]
            label_counts[hate_label] = label_counts.get(hate_label, 0) + 1
            row_id = f"latent_{ann['ID']}"

            fields = [row_id, '', '', text, 'no', hate_label, 'none']
            f.write('\t'.join(fields) + '\n')
            rows_out += 1

    print(f'Wrote {rows_out} auxiliary rows -> {args.out}')
    for k in ('yes_implicit', 'yes_explicit', 'no'):
        print(f'  {k:<14}: {label_counts.get(k, 0)}')
    print('NOTE: train the hate_speech head only; mask stereotype/target losses on these rows.')


if __name__ == '__main__':
    main()