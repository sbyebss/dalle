### 04/23/2022

Dataset:

- [x] need to add another dataloader
- [x] how to make it to be unpaired data?

Loss:

- [ ] need to add optimizer for discriminator
- [ ] need to add two loops (easy)
- [ ] need to add discriminator in the dalle_pytorch forward()
- [ ] (optional) we may need a adaptive weight for generator as well like eq 7 in VQGAN.

Details:

- [seems_not] see whether I need masks in doing Gromov distance

From taming code, I see that the input of encoder and discriminator are the same tensor. We don't need to implement forward for VQGAN because our fake image is not from VQGAN.

I find we need to use resampling to generate fake images! totally different with cross-entropy training! They input both text and image into the transformer.

- [ ] need to make sure the format of fake image is the same as real image

Paper:

- [ ] see what do they compare?

Before I change: their optimizer includes parameters of
xxx_emb, transformer, to_logits. All of these should be distributed as generator parameters.

My concern:

- [ ] discriminator is too weak

- [ ] augoregressiv model as generator is too slow

### 4/24/2022

I find I need to decrease it to O(n^2). Otherwise I'll give it up. And I cannot pushforward everything for additional text dataset in advance because T(x) for those texts are also in the training. So all the pushforward have to be done in the loss function.
