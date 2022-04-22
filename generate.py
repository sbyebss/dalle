import argparse
from pathlib import Path
from tqdm import tqdm
from collections import OrderedDict
# torch

import torch

from einops import repeat

# vision imports

from torchvision.utils import save_image

# dalle related classes and utils

from dalle_pytorch import DiscreteVAE, OpenAIDiscreteVAE, VQGanVAE, DALLE
from dalle_pytorch.tokenizer import tokenizer, HugTokenizer, YttmTokenizer, ChineseTokenizer

# argument parsing

parser = argparse.ArgumentParser()

parser.add_argument('--dalle_path', type=str,
                    # required=True,
                    default='/home/jfan97/dpmodel/dalle/16L_64HD_8H_512I_128T_cc12m_cc3m_3E.pth',
                    help='path to your trained DALL-E')

parser.add_argument('--vqgan_model_path', type=str,
                    default="/home/jfan97/dpmodel/dalle/vqgan_imagenet_f16_1024.ckpt",
                    help='path to your trained VQGAN weights. This should be a .ckpt file. (only valid when taming option is enabled)')

parser.add_argument('--vqgan_config_path', type=str,
                    default="/home/jfan97/dpmodel/dalle/vqgan_imagenet_f16_1024_config.yml",
                    help='path to your trained VQGAN config. This should be a .yaml file.  (only valid when taming option is enabled)')

parser.add_argument('--text', type=str,
                    # required=True,
                    default='fireflies in a field under a full moon',
                    help='your text prompt')

parser.add_argument('--num_images', type=int, default=128, required=False,
                    help='number of images')

parser.add_argument('--batch_size', type=int, default=4, required=False,
                    help='batch size')

parser.add_argument('--top_k', type=float, default=0.9, required=False,
                    help='top k filter threshold')

parser.add_argument('--outputs_dir', type=str, default='./outputs', required=False,
                    help='output directory')

parser.add_argument('--bpe_path', type=str,
                    help='path to your huggingface BPE json file')

parser.add_argument('--hug', dest='hug', action='store_true')

parser.add_argument('--chinese', dest='chinese', action='store_true')

parser.add_argument('--taming', dest='taming',
                    default=True, action='store_true')

parser.add_argument('--gentxt', dest='gentxt', action='store_true')

args = parser.parse_args()

# helper fns


def exists(val):
    return val is not None

# tokenizer


if exists(args.bpe_path):
    klass = HugTokenizer if args.hug else YttmTokenizer
    tokenizer = klass(args.bpe_path)
elif args.chinese:
    tokenizer = ChineseTokenizer()

# load DALL-E

dalle_path = Path(args.dalle_path)

assert dalle_path.exists(), 'trained DALL-E must exist'

load_obj = torch.load(str(dalle_path))
dalle_params, vae_params, weights, vae_class_name, version = load_obj.pop('hparams'), load_obj.pop(
    'vae_params'), load_obj.pop('weights'), load_obj.pop('vae_class_name', None), load_obj.pop('version', None)

# friendly print

if exists(version):
    print(f'Loading a model trained with DALLE-pytorch version {version}')
else:
    print('You are loading a model trained on an older version of DALL-E pytorch - it may not be compatible with the most recent version')

# load VAE

if args.taming:
    vae = VQGanVAE(args.vqgan_model_path, args.vqgan_config_path)
elif vae_params is not None:
    vae = DiscreteVAE(**vae_params)
else:
    vae = OpenAIDiscreteVAE()

assert not (exists(vae_class_name) and vae.__class__.__name__ !=
            vae_class_name), f'you trained DALL-E using {vae_class_name} but are trying to generate with {vae.__class__.__name__} - please make sure you are passing in the correct paths and settings for the VAE to use for generation'

# reconstitute DALL-E
# dalle_params['attn_types'] = ('axial_col',)
# dalle = DALLE(vae=vae, **dalle_params).cuda()
dalle = DALLE(vae=vae, **dalle_params, rotary_emb=False,
              shift_tokens=False,
              #   optimize_for_inference=True
              ).cuda()

weights = OrderedDict([(key.replace('to_qkv', 'fn.to_qkv').replace('to_out', 'fn.to_out').replace('attn_fn', 'fn.attn_fn'), value)
                       for key, value in weights.items()])
dalle.load_state_dict(weights)
dalle = dalle.half()

# generate images

image_size = vae.image_size

texts = args.text.split('|')

for j, text in tqdm(enumerate(texts)):
    if args.gentxt:
        text_tokens, gen_texts = dalle.generate_texts(
            tokenizer, text=text, filter_thres=args.top_k)
        text = gen_texts[0]
    else:
        text_tokens = tokenizer.tokenize([text], dalle.text_seq_len).cuda()

    text_tokens = repeat(text_tokens, '() n -> b n', b=args.num_images)

    outputs = []

    for text_chunk in tqdm(text_tokens.split(args.batch_size), desc=f'generating images for - {text}'):
        output = dalle.generate_images(
            text_chunk, filter_thres=args.top_k,
            # use_cache=True
        )
        outputs.append(output)

    outputs = torch.cat(outputs)

    # save all images

    file_name = text
    outputs_dir = Path(args.outputs_dir) / file_name.replace(' ', '_')[:(100)]
    outputs_dir.mkdir(parents=True, exist_ok=True)

    for i, image in tqdm(enumerate(outputs), desc='saving images'):
        save_image(image, outputs_dir / f'{i}.jpg', normalize=True)
        with open(outputs_dir / 'caption.txt', 'w') as f:
            f.write(file_name)

    print(f'created {args.num_images} images at "{str(outputs_dir)}"')
